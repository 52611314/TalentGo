from decimal import Decimal, ROUND_HALF_UP
from app.schemas.evaluation import DIMENSIONS

WEIGHTS = {
    'technical': dict(zip(DIMENSIONS, [15, 30, 25, 20, 10])),
    'behavioral': dict(zip(DIMENSIONS, [15, 15, 20, 35, 15])),
    'pressure': dict(zip(DIMENSIONS, [20, 20, 25, 20, 15])),
}
RUBRIC_VERSION = 'rubric-1.0'
PROMPT_VERSION = 'prompt-1.0'


def rounded(value):
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def question_score(dimensions, mode):
    weights = WEIGHTS[mode]
    scored = [(Decimal(str(dimensions[key]['score'])), Decimal(weights[key]))
              for key in DIMENSIONS if dimensions[key]['score'] is not None]
    if not scored:
        return None
    return rounded(Decimal(100) * sum(score / 5 * weight for score, weight in scored) / sum(w for _, w in scored))


def aggregate(evaluations):
    scores = [Decimal(str(e['question_score'])) for e in evaluations if e['question_score'] is not None]
    dimensions = {}
    for key in DIMENSIONS:
        values = [Decimal(str(e['dimensions'][key]['score'])) for e in evaluations if e['dimensions'][key]['score'] is not None]
        dimensions[key] = float(rounded(sum(values) / len(values))) if values else None
    return rounded(sum(scores) / len(scores)) if scores else None, dimensions


def validate_evidence(evaluation, messages):
    allowed = {str(m['id']): m['content'] for m in messages if m['speaker'] == 'user' and m['kind'] == 'answer'}
    for dimension in evaluation.dimensions.model_dump().values():
        for evidence in dimension['evidence']:
            source = allowed.get(str(evidence['message_id']))
            if source is None or evidence['quote'] not in source:
                raise ValueError('Evidence must exactly quote a user answer from this question')


def decide_followup(evaluation, used, budget, hint_used):
    if used >= budget:
        return None, False
    if evaluation.flag == 'idk':
        return (evaluation.followup or '可以先从你确定的部分开始，说明一个基本概念与例子。', True) if not hint_used else (None, False)
    scores = [Decimal(str(d.score)) for d in evaluation.dimensions.__dict__.values() if d.score is not None]
    weak = scores and sum(scores) / len(scores) < 3
    if evaluation.flag in {'vague', 'off_topic', 'critical_error'} or (weak and evaluation.missing_points):
        return evaluation.followup or '请针对本题补充一个具体例子，并说明结论的理由。', False
    return None, False


def next_difficulty(evaluation, current):
    values = [d.score for d in evaluation.dimensions.__dict__.values() if d.score is not None]
    if not values:
        return current
    mean = sum(values) / len(values)
    if mean >= 4 and evaluation.flag != 'critical_error':
        return min(3, current + 1)
    if mean < 2:
        return max(1, current - 1)
    return current
