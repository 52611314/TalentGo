from datetime import datetime, timedelta
from uuid import UUID

from app.models import Question
from app.services.interview import now
from test_interview import action, answer, create, get, identity, messages, mutation
from test_m3 import provider


def expire(client, question_id):
    with client.app.state.session_factory() as db:
        db.get(Question, UUID(question_id)).answer_deadline_at = now() - timedelta(seconds=1)
        db.commit()


def test_pause_expiry_and_next_turn_persist_across_reads(client):
    h = identity(client)
    sid = create(client, h, config={'question_count': 2, 'answer_time_seconds': 60})['id']
    action(client, h, sid, 'start')
    q = get(client, h, sid)['current_question']
    assert q['answer_deadline_at']
    action(client, h, sid, 'pause')
    paused = get(client, h, sid)['current_question']
    assert paused['answer_deadline_at'] is None and 0 < paused['answer_remaining_ms'] <= 60000
    action(client, h, sid, 'resume')
    resumed = get(client, h, sid)
    assert resumed['current_question']['answer_remaining_ms'] is None
    assert datetime.fromisoformat(resumed['current_question']['answer_deadline_at']) > now()
    early = client.post(f'/api/v1/sessions/{sid}/actions', headers=mutation(h),
                        json={'expected_version': resumed['version'], 'action': 'time_expired'})
    assert early.json()['error']['code'] == 'ANSWER_TIME_REMAINING'
    expire(client, q['id'])
    late = client.post(f'/api/v1/sessions/{sid}/messages', headers=mutation(h),
                       json={'expected_version': resumed['version'], 'kind': 'answer', 'question_id': q['id'], 'content': '迟到草稿'})
    assert late.json()['error']['code'] == 'ANSWER_TIME_EXPIRED'
    action(client, h, sid, 'time_expired')
    next_q = get(client, h, sid)['current_question']
    assert next_q['ordinal'] == 2 and datetime.fromisoformat(next_q['answer_deadline_at']) > now()
    assert not [m for m in messages(client, h, sid) if m['kind'] == 'answer']


def test_followup_gets_own_clock_and_timeout_keeps_original_answer(client, provider):
    h = identity(client)
    sid = create(client, h, provider='deepseek', config={
        'question_count': 1, 'max_followups': 1, 'answer_time_seconds': 60,
    })['id']
    action(client, h, sid, 'start')
    original = get(client, h, sid)['current_question']
    answer(client, h, sid, '模糊')
    followup = get(client, h, sid)['current_question']
    assert followup['id'] == original['id'] and followup['followup_count'] == 1
    assert followup['answer_deadline_at'] > original['answer_deadline_at']
    expire(client, followup['id'])
    action(client, h, sid, 'time_expired')
    report = client.get(f'/api/v1/sessions/{sid}/report', headers=h).json()['data']
    assert report['status'] == 'ready' and report['coverage']['scored'] == 1
    assert [m['content'] for m in report['messages'] if m['kind'] == 'answer'] == ['模糊']


def test_scoring_and_next_question_have_ordered_phase_events(client, provider):
    h = identity(client)
    sid = create(client, h, provider='deepseek')['id']
    action(client, h, sid, 'start')
    result, _ = answer(client, h, sid)
    events = client.get(f"/api/v1/operations/{result['operation_id']}/events", headers=h).text
    assert events.index('event: operation.phase\ndata: {"phase": "evaluate"') < events.index(
        'event: operation.phase_completed\ndata: {"phase": "evaluate"') < events.index(
        'event: operation.phase\ndata: {"phase": "question"') < events.index(
        'event: operation.phase_completed\ndata: {"phase": "question"')
    assert events.count('event: text.delta') == 1
