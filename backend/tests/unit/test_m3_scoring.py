import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.agent.context_builder import build_context, seed_question
from app.agent.skill_registry import select_skill
from app.core.errors import AppError
from app.schemas.evaluation import AnswerEvaluation, DIMENSIONS
from app.services.scoring import aggregate, decide_followup, next_difficulty, question_score, validate_evidence


def evaluation(score=3, flag='normal', **values):
    mid = str(uuid.uuid4())
    return AnswerEvaluation.model_validate({'dimensions': {key: {'score': score, 'reason': '依据本题回答',
        'evidence': [{'message_id': mid, 'quote': '具体回答'}] if score is not None else []} for key in DIMENSIONS},
        'flag': flag, 'missing_points': ['补充理由'], 'suggestion': '解释边界与例子', 'followup': '请补充一个具体例子。', **values})


@pytest.mark.parametrize('mode', ['technical', 'behavioral', 'pressure'])
@pytest.mark.parametrize('score,expected', [(0, Decimal('0')), (3, Decimal('60')), (5, Decimal('100')), (None, None)])
def test_normalized_scores(mode, score, expected):
    assert question_score(evaluation(score).model_dump()['dimensions'], mode) == expected


def test_missing_dimensions_and_final_average():
    dims = evaluation(None).model_dump()['dimensions']
    dims['relevance']['score'] = 4
    dims['accuracy_consistency']['score'] = 3
    assert question_score(dims, 'technical') == Decimal('66.67')
    dims2 = evaluation(5).model_dump()['dimensions']
    total, averages = aggregate([{'dimensions': dims, 'question_score': '66.67'},
        {'dimensions': dims2, 'question_score': 100}, {'dimensions': evaluation(None).model_dump()['dimensions'], 'question_score': None}])
    assert total == Decimal('83.34')
    assert averages['relevance'] == 4.5 and averages['reasoning'] == 5
    assert aggregate([])[0] is None


@pytest.mark.parametrize('score', [-1, 6, 'NaN', '1.234'])
def test_invalid_score_rejected(score):
    with pytest.raises(ValidationError):
        evaluation(score)


def test_evidence_cannot_quote_other_or_assistant_message():
    value = evaluation()
    mid = str(value.dimensions.relevance.evidence[0].message_id)
    good = {'id': mid, 'speaker': 'user', 'kind': 'answer', 'content': '这是具体回答的原文'}
    validate_evidence(value, [good])
    for altered in [{**good, 'speaker': 'assistant'}, {**good, 'kind': 'clarification'},
                    {**good, 'id': str(uuid.uuid4())}, {**good, 'content': '改写过的资料'}]:
        with pytest.raises(ValueError):
            validate_evidence(value, [altered])


def test_nonnull_requires_evidence():
    data = evaluation().model_dump()
    data['dimensions']['reasoning']['evidence'] = []
    with pytest.raises(ValidationError):
        AnswerEvaluation.model_validate(data)


def test_followup_and_difficulty_rules():
    assert decide_followup(evaluation(2, 'vague'), 0, 1, False)[0]
    assert decide_followup(evaluation(2, 'vague'), 1, 1, False) == (None, False)
    assert decide_followup(evaluation(None, 'idk'), 0, 2, False)[1]
    assert decide_followup(evaluation(None, 'idk'), 1, 2, True) == (None, False)
    assert decide_followup(evaluation(4), 0, 2, False) == (None, False)
    assert next_difficulty(evaluation(5), 2) == 3
    assert next_difficulty(evaluation(5), 3) == 3
    assert next_difficulty(evaluation(1), 1) == 1
    assert next_difficulty(evaluation(1), 3) == 2


def test_skill_triggers_and_seed_coverage():
    for mode in ('technical', 'behavioral', 'pressure'):
        assert select_skill({'mode': mode, 'config': {'pressure_consent': True}}).key == mode
        for role in ('frontend', 'backend'):
            seeds = [seed_question(role, mode, i) for i in range(1, 11)]
            assert len({s['source_key'] for s in seeds}) == 10
            assert all(s['anchors'] for s in seeds)
    assert select_skill({'finishing': True}).key == 'review'
    with pytest.raises(AppError):
        select_skill({'mode': 'pressure', 'config': {'pressure_consent': False}})


def test_context_drops_old_history_but_never_slices_current_answer():
    snapshot = {'role': 'frontend', 'mode': 'technical', 'config': {}, 'profile_snapshot': {},
        'question': {}, 'thread': [{'content': '完整当前答案'}], 'previous_questions': [], 'history': [{'content': '旧资料' * 10000}]}
    context = build_context(snapshot, {}, 18000)
    assert not context['recent_history'] and context['thread'] == snapshot['thread']
    snapshot['thread'] = [{'content': '当前资料' * 10000}]
    with pytest.raises(AppError) as error:
        build_context(snapshot, {}, 18000)
    assert error.value.code == 'CONTEXT_TOO_LONG'
