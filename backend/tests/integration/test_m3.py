"""Fixture provider tests exercise real orchestration, not external model quality."""
import threading
import time
import uuid

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.core.errors import AppError
from app.llm.base import ModelResult
from app.models import Evaluation
from app.schemas.evaluation import DIMENSIONS
from test_interview import action, answer, create, get, identity, messages, mutation, wait


class FixtureProvider:
    def __init__(self):
        self.calls = []
        self.fail = False
        self.block = False
        self.entered = threading.Event()

    def generate(self, schema, system, context, check, validate=None):
        self.calls.append(schema.__name__)
        check()
        if self.fail:
            raise AppError(503, 'MODEL_RATE_LIMITED', '测试限额失败')
        if self.block:
            self.entered.set()
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                check()
                time.sleep(.01)
            raise AssertionError('Cancellation did not reach provider')
        name = schema.__name__
        if name == 'GeneratedQuestion':
            data = {'topic': context['seed']['topic'], 'question': context['seed']['question']}
        elif name == 'GeneratedHint':
            data = {'hint': '先从概念和一个例子开始说明。'}
        elif name == 'ClarifiedGoal':
            data = {'role': context['known_role'] or 'backend', 'mode': context['known_mode'] or 'behavioral', 'reply': '目标已确认，请检查配置后开始。'}
        elif name == 'AnswerEvaluation':
            source = [m for m in context['thread'] if m['speaker'] == 'user' and m['kind'] == 'answer'][-1]
            vague = source['content'] == '模糊'
            unknown = source['content'] == '不会'
            score = None if unknown else 2 if vague else 4
            data = {'dimensions': {key: {'score': score, 'reason': '本题材料的固定测试评价',
                'evidence': [] if unknown else [{'message_id': source['id'], 'quote': source['content'][:40]}]} for key in DIMENSIONS},
                'flag': 'idk' if unknown else 'vague' if vague else 'normal', 'missing_points': ['补充测试与边界'] if vague else [],
                'suggestion': '下次补充边界与例子。', 'followup': '请补充一个具体例子。' if vague or unknown else None}
        elif name == 'InterviewReview':
            qid = context['evaluations'][0]['question_id']
            data = {'summary': '固定夹具复盘，不代表真实模型效果。', 'strengths': [{'text': '回答提供了依据。', 'question_ids': [qid]}],
                    'gaps': [], 'recommendations': [{'text': '复习边界。', 'question_ids': [qid]}]}
        else:
            raise AssertionError(name)
        value = schema.model_validate(data)
        if validate:
            validate(value)
        return ModelResult(value, 10, 20, 1, 1)


@pytest.fixture
def provider(client, test_app):
    old_key = test_app.state.settings.llm_api_key
    old_factory = test_app.state.runner.real.provider_factory
    value = FixtureProvider()
    test_app.state.settings.llm_api_key = SecretStr('fixture-key')
    test_app.state.runner.real.provider_factory = lambda _: value
    yield value
    test_app.state.runner.real.provider_factory = old_factory
    test_app.state.settings.llm_api_key = old_key


def real_session(client, headers, mode='technical', count=1, followups=0, **values):
    return create(client, headers, provider='deepseek', mode=mode,
        config={'question_count': count, 'max_followups': followups, 'pressure_consent': mode == 'pressure'}, **values)


def report(client, headers, sid):
    return client.get(f'/api/v1/sessions/{sid}/report', headers=headers).json()['data']


@pytest.mark.parametrize('mode', ['technical', 'behavioral', 'pressure'])
def test_real_three_modes_four_skills_and_evidence(client, provider, mode):
    headers = identity(client)
    session = real_session(client, headers, mode)
    sid = session['id']
    from app.services.scoring import RUBRIC_VERSION
    assert not session['is_mock'] and session['rubric_version'] == RUBRIC_VERSION
    action(client, headers, sid, 'start')
    text = '我先解释结论，再用具体项目说明测试边界。'
    answer(client, headers, sid, text)
    result = report(client, headers, sid)
    assert result['total_score'] == 80 and result['coverage']['scored'] == 1
    assert result['dimension_scores']['reasoning'] == 4
    assert len(result['question_evaluations']) == 1
    evidence = result['question_evaluations'][0]['dimensions']['reasoning']['evidence'][0]
    assert evidence['quote'] == text
    assert next(m for m in result['messages'] if m['id'] == evidence['message_id'])['speaker'] == 'user'
    trace = client.get(f'/api/v1/sessions/{sid}/trace', headers=headers).json()['data']['items']
    assert {t['skill_key'] for t in trace} == {mode, 'review'}
    assert all(t['usage']['input_tokens'] == 10 for t in trace)
    stranger = identity(client)
    assert client.get(f'/api/v1/sessions/{sid}/trace', headers=stranger).status_code == 404


def test_followup_has_one_final_grade_and_promotes_cached_answer(client, test_app, provider):
    h = identity(client)
    sid = real_session(client, h, followups=1)['id']
    action(client, h, sid, 'start')
    answer(client, h, sid, '模糊')
    assert get(client, h, sid)['current_question']['followup_count'] == 1
    assert get(client, h, sid)['coverage']['scored'] == 0
    before = provider.calls.count('AnswerEvaluation')
    action(client, h, sid, 'finish')
    assert provider.calls.count('AnswerEvaluation') == before
    assert report(client, h, sid)['total_score'] == 40
    with test_app.state.session_factory() as db:
        rows = db.scalars(select(Evaluation).where(Evaluation.session_id == uuid.UUID(sid))).all()
        assert sorted(r.scope for r in rows) == ['final', 'provisional']


def test_followup_final_replaces_provisional_for_average(client, provider):
    h = identity(client); sid = real_session(client, h, followups=1)['id']
    action(client, h, sid, 'start'); answer(client, h, sid, '模糊')
    answer(client, h, sid, '我用具体例子补充边界和测试方法。')
    assert report(client, h, sid)['total_score'] == 80
    assert len(report(client, h, sid)['question_evaluations']) == 1


def test_idk_hint_once_and_all_null_grade(client, provider):
    h = identity(client); sid = real_session(client, h, followups=2)['id']
    action(client, h, sid, 'start'); answer(client, h, sid, '不会')
    assert get(client, h, sid)['current_question']['hint_used']
    assert provider.calls.count('GeneratedHint') == 1
    answer(client, h, sid, '不会')
    result = report(client, h, sid)
    assert result['total_score'] is None and result['coverage']['scored'] == 0
    assert provider.calls.count('GeneratedHint') == 1


def test_skip_excludes_provisional_and_empty_finish(client, provider):
    h = identity(client); sid = real_session(client, h, count=2, followups=1)['id']
    action(client, h, sid, 'start'); answer(client, h, sid, '模糊')
    action(client, h, sid, 'skip'); action(client, h, sid, 'finish')
    result = report(client, h, sid)
    assert result['total_score'] is None and not result['question_evaluations']
    assert result['coverage']['skipped'] == 1
    assert 'InterviewReview' not in provider.calls


def test_real_error_does_not_fallback_and_retry_reuses_input(client, provider):
    h = identity(client); sid = real_session(client, h)['id']
    action(client, h, sid, 'start'); provider.fail = True
    data, _ = answer(client, h, sid, '保留这条已保存的答案。', wait_for=False)
    assert wait(client, h, data['operation_id'], 'failed')['error_code'] == 'MODEL_RATE_LIMITED'
    assert len([m for m in messages(client, h, sid) if m['kind'] == 'answer']) == 1
    assert get(client, h, sid)['coverage']['scored'] == 0
    provider.fail = False
    retried = client.post(f"/api/v1/operations/{data['operation_id']}/retry", json={}, headers=mutation(h))
    assert retried.status_code == 202
    wait(client, h, data['operation_id'])
    assert len([m for m in report(client, h, sid)['messages'] if m['kind'] == 'answer']) == 1
    assert report(client, h, sid)['total_score'] == 80


def test_cancellation_during_model_never_commits_candidate(client, provider):
    h = identity(client); sid = real_session(client, h)['id']; provider.block = True
    data = action(client, h, sid, 'start', wait_for=False)
    assert provider.entered.wait(3)
    cancelled = client.post(f"/api/v1/operations/{data['operation_id']}/cancel", json={}, headers=mutation(h))
    assert cancelled.status_code == 200
    wait(client, h, data['operation_id'], 'cancelled')
    assert get(client, h, sid)['current_question'] is None
    trace = client.get(f'/api/v1/sessions/{sid}/trace', headers=h).json()['data']['items']
    assert trace[0]['status'] == 'cancelled'


def test_real_natural_clarification_and_model_status(client, provider):
    h = identity(client); sid = real_session(client, h, mode=None, role=None)['id']
    current = get(client, h, sid)
    response = client.post(f'/api/v1/sessions/{sid}/messages', headers=mutation(h),
        json={'expected_version': current['version'], 'kind': 'clarification', 'content': '我想练服务端项目经历的表达'})
    wait(client, h, response.json()['data']['operation_id'])
    assert get(client, h, sid)['mode'] == 'behavioral'
    assert get(client, h, sid)['role'] == 'backend'
    status = client.get('/api/v1/models/status', headers=h)
    assert status.status_code == 200 and 'fixture-key' not in status.text
    assert len(status.json()['data']['skills']) == 4


def test_missing_key_prevents_real_session_without_affecting_mock(client, test_app, provider):
    test_app.state.settings.llm_api_key = None
    h = identity(client)
    response = client.post('/api/v1/sessions', headers=mutation(h), json={'provider': 'deepseek'})
    assert response.status_code == 503 and response.json()['error']['code'] == 'MODEL_NOT_CONFIGURED'
    assert create(client, h)['is_mock']
