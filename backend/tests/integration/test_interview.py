import secrets
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from sqlalchemy import func, select, text

from app.models import InterviewSession, Message, Operation, OperationEvent, Question, User
from app.schemas.session import SessionAction
from app.services.interview import now, submit
from app.core.security import hash_secret
from app.models import Profile
from fastapi.testclient import TestClient


def identity(client):
    data = client.post('/api/v1/identity', json={'display_name': 'M2 测试'},
                       headers={'Idempotency-Key': secrets.token_hex(32)}).json()['data']
    return {'Authorization': 'Bearer ' + data['token']}


def mutation(headers, key=None):
    return {**headers, 'Idempotency-Key': key or secrets.token_hex(16)}


def create(client, headers, **values):
    payload = {'role': 'frontend', 'mode': 'technical',
               'config': {'question_count': 2, 'max_followups': 0}, **values}
    result = client.post('/api/v1/sessions', json=payload, headers=mutation(headers))
    assert result.status_code == 201, result.text
    return result.json()['data']


def get(client, headers, sid):
    result = client.get(f'/api/v1/sessions/{sid}', headers=headers)
    assert result.status_code == 200, result.text
    return result.json()['data']


def wait(client, headers, oid, expected='succeeded'):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        result = client.get(f'/api/v1/operations/{oid}', headers=headers).json()['data']
        if result['status'] in {'succeeded', 'failed', 'cancelled'}:
            assert result['status'] == expected, result
            return result
        time.sleep(0.01)
    pytest.fail('Operation did not reach a terminal state')


def action(client, headers, sid, name, wait_for=True, **extra):
    session = get(client, headers, sid)
    result = client.post(f'/api/v1/sessions/{sid}/actions', headers=mutation(headers),
                         json={'expected_version': session['version'], 'action': name, **extra})
    assert result.status_code in {200, 202}, result.text
    data = result.json()['data']
    if data['operation_id'] and wait_for:
        wait(client, headers, data['operation_id'])
    return data


def answer(client, headers, sid, content='这是一个足够具体的回答。' * 8, wait_for=True, key=None):
    session = get(client, headers, sid)
    body = {'expected_version': session['version'], 'kind': 'answer', 'question_id': session['current_question']['id'], 'content': content}
    result = client.post(f'/api/v1/sessions/{sid}/messages', headers=mutation(headers, key), json=body)
    assert result.status_code == 202, result.text
    if wait_for:
        wait(client, headers, result.json()['data']['operation_id'])
    return result.json()['data'], body


def messages(client, headers, sid):
    return client.get(f'/api/v1/sessions/{sid}/messages', headers=headers).json()['data']['items']


def test_complete_mock_interview_and_report(client):
    headers = identity(client)
    session = create(client, headers)
    assert session['status'] == 'ready'
    action(client, headers, session['id'], 'start')
    answer(client, headers, session['id'])
    assert get(client, headers, session['id'])['current_question']['ordinal'] == 2
    answer(client, headers, session['id'])
    final = get(client, headers, session['id'])
    assert final['status'] == 'completed'
    report = client.get(f"/api/v1/sessions/{session['id']}/report", headers=headers).json()['data']
    assert report['status'] == 'ready' and report['is_mock'] is True
    assert report['coverage']['answered'] == 2
    assert report['total_score'] is None and report['dimension_scores'] == {}
    assert len([m for m in report['messages'] if m['kind'] == 'answer']) == 2


def test_clarification_persists_and_uses_explicit_choices(client):
    headers = identity(client)
    session = create(client, headers, role=None, mode=None)
    assert session['status'] == 'clarifying'
    action(client, headers, session['id'], 'clarify')
    current = get(client, headers, session['id'])
    result = client.post(f"/api/v1/sessions/{session['id']}/messages", headers=mutation(headers),
                        json={'expected_version': current['version'], 'kind': 'clarification', 'content': '前端 技术'})
    wait(client, headers, result.json()['data']['operation_id'])
    current = get(client, headers, session['id'])
    assert (current['role'], current['mode'], current['status']) == ('frontend', 'technical', 'ready')
    assert len(messages(client, headers, session['id'])) == 3


def test_invalid_state_and_pressure_consent(client):
    headers = identity(client)
    session = create(client, headers, mode='pressure')
    result = client.post(f"/api/v1/sessions/{session['id']}/actions", headers=mutation(headers),
                        json={'expected_version': session['version'], 'action': 'start'})
    assert result.status_code == 409
    assert result.json()['error']['code'] == 'PRESSURE_CONSENT_REQUIRED'
    updated = client.patch(f"/api/v1/sessions/{session['id']}", headers=mutation(headers),
                           json={'expected_version': session['version'], 'config': {'pressure_consent': True, 'pressure_level': 3}})
    assert updated.status_code == 200
    action(client, headers, session['id'], 'start')
    action(client, headers, session['id'], 'lower_pressure', pressure_level=1)
    assert get(client, headers, session['id'])['config']['pressure_level'] == 1


def test_followup_budget_and_single_hint(client):
    headers = identity(client)
    session = create(client, headers, config={'question_count': 2, 'max_followups': 1})
    action(client, headers, session['id'], 'start')
    action(client, headers, session['id'], 'hint')
    current = get(client, headers, session['id'])
    result = client.post(f"/api/v1/sessions/{session['id']}/actions", headers=mutation(headers),
                        json={'expected_version': current['version'], 'action': 'hint'})
    assert result.status_code == 409
    answer(client, headers, session['id'], '简短回答')
    assert get(client, headers, session['id'])['current_question']['followup_count'] == 1
    answer(client, headers, session['id'], '再简短也不能无限追问')
    assert get(client, headers, session['id'])['current_question']['ordinal'] == 2


def test_pause_resume_skip_and_early_finish(client):
    headers = identity(client)
    session = create(client, headers, config={'question_count': 5})
    action(client, headers, session['id'], 'start')
    action(client, headers, session['id'], 'pause')
    assert get(client, headers, session['id'])['status'] == 'paused'
    action(client, headers, session['id'], 'resume')
    action(client, headers, session['id'], 'skip')
    action(client, headers, session['id'], 'finish')
    report = client.get(f"/api/v1/sessions/{session['id']}/report", headers=headers).json()['data']
    assert report['coverage'] == {'planned': 5, 'asked': 2, 'answered': 0, 'skipped': 1, 'not_reached': 3, 'scored': 0}
    assert report['total_score'] is None


def test_started_configuration_is_immutable_and_version_checked(client):
    headers = identity(client)
    session = create(client, headers)
    action(client, headers, session['id'], 'start')
    result = client.patch(f"/api/v1/sessions/{session['id']}", headers=mutation(headers), json={'expected_version': 1, 'role': 'backend'})
    assert result.status_code == 409 and result.json()['error']['code'] == 'VERSION_CONFLICT'
    current = get(client, headers, session['id'])
    assert client.patch(f"/api/v1/sessions/{session['id']}", headers=mutation(headers),
                        json={'expected_version': current['version'], 'role': 'backend'}).status_code == 409


def test_shared_idempotency_and_answer_replay(client):
    headers = identity(client)
    key = secrets.token_hex(16)
    body = {'role': 'backend', 'mode': 'technical', 'config': {'question_count': 1, 'max_followups': 0}}
    first = client.post('/api/v1/sessions', headers=mutation(headers, key), json=body)
    second = client.post('/api/v1/sessions', headers=mutation(headers, key), json=body)
    assert first.json()['data']['id'] == second.json()['data']['id']
    assert client.patch('/api/v1/profile', headers=mutation(headers, key), json={'expected_version': 1, 'goals': 'collision'}).status_code == 409
    sid = first.json()['data']['id']
    action(client, headers, sid, 'start')
    answer_key = secrets.token_hex(16)
    accepted, payload = answer(client, headers, sid, key=answer_key)
    repeated = client.post(f'/api/v1/sessions/{sid}/messages', headers=mutation(headers, answer_key), json=payload)
    assert repeated.json()['data']['operation_id'] == accepted['operation_id']
    assert len([m for m in messages(client, headers, sid) if m['kind'] == 'answer']) == 1


def test_cancel_retry_preserves_one_answer(client):
    headers = identity(client)
    session = create(client, headers)
    sid = session['id']
    action(client, headers, sid, 'start')
    client.app.state.runner.delay = 0.1
    try:
        accepted, _ = answer(client, headers, sid, '短回答', wait_for=False)
        oid = accepted['operation_id']
        assert client.post(f'/api/v1/operations/{oid}/cancel', headers=mutation(headers)).status_code == 200
        wait(client, headers, oid, 'cancelled')
        current = get(client, headers, sid)
        duplicate = client.post(f'/api/v1/sessions/{sid}/messages', headers=mutation(headers),
            json={'expected_version': current['version'], 'kind': 'answer', 'content': '再次发送', 'question_id': current['current_question']['id']})
        assert duplicate.status_code == 409 and duplicate.json()['error']['code'] == 'OPERATION_RETRY_REQUIRED'
        client.app.state.runner.delay = 0.001
        retried = client.post(f'/api/v1/operations/{oid}/retry', headers=mutation(headers))
        assert retried.status_code == 202
        wait(client, headers, oid)
        assert len([m for m in messages(client, headers, sid) if m['kind'] == 'answer']) == 1
        assert get(client, headers, sid)['latest_operation']['attempt_no'] == 2
    finally:
        client.app.state.runner.delay = 0.001


def test_failed_generation_and_retry(client, monkeypatch):
    headers = identity(client)
    session = create(client, headers)
    provider = client.app.state.runner.provider
    original = provider.question
    monkeypatch.setattr(provider, 'question', lambda *args: (_ for _ in ()).throw(RuntimeError('fixture failure')))
    accepted = action(client, headers, session['id'], 'start', wait_for=False)
    wait(client, headers, accepted['operation_id'], 'failed')
    assert get(client, headers, session['id'])['current_question'] is None
    monkeypatch.setattr(provider, 'question', original)
    client.post(f"/api/v1/operations/{accepted['operation_id']}/retry", headers=mutation(headers))
    wait(client, headers, accepted['operation_id'])
    assert get(client, headers, session['id'])['status'] == 'interviewing'


def test_process_interruption_recovery_does_not_generate_on_get(client):
    headers = identity(client)
    session = create(client, headers)
    with client.app.state.session_factory() as db:
        user = db.scalar(select(User))
        accepted = submit(db, user.id, uuid.UUID(session['id']), SessionAction(expected_version=1, action='start'), 'unqueued-fixture')
    oid = accepted['operation_id']
    assert client.get(f'/api/v1/operations/{oid}', headers=headers).json()['data']['status'] == 'queued'
    client.app.state.runner.recover_interrupted()
    result = wait(client, headers, oid, 'failed')
    assert result['error_code'] == 'PROCESS_INTERRUPTED'
    assert get(client, headers, session['id'])['current_question'] is None
    client.post(f'/api/v1/operations/{oid}/retry', headers=mutation(headers))
    wait(client, headers, oid)


def test_sse_replay_resume_and_invalid_cursor(client):
    headers = identity(client)
    session = create(client, headers)
    accepted = action(client, headers, session['id'], 'start')
    oid = accepted['operation_id']
    stream = client.get(f'/api/v1/operations/{oid}/events', headers=headers)
    assert stream.status_code == 200 and 'text/event-stream' in stream.headers['content-type']
    assert 'operation.started' in stream.text and 'operation.succeeded' in stream.text
    event_ids = [line[4:] for line in stream.text.splitlines() if line.startswith('id: ')]
    assert len(event_ids) == len(set(event_ids))
    resumed = client.get(f'/api/v1/operations/{oid}/events', headers={**headers, 'Last-Event-ID': event_ids[1]})
    assert event_ids[0] not in resumed.text and event_ids[1] not in resumed.text
    assert client.get(f'/api/v1/operations/{oid}/events', headers={**headers, 'Last-Event-ID': f'{uuid.uuid4()}:1'}).status_code == 400
    with client.app.state.session_factory() as db:
        db.get(Operation, uuid.UUID(oid)).finished_at = now() - timedelta(days=8)
        db.commit()
    assert client.get(f'/api/v1/operations/{oid}/events', headers=headers).status_code == 410


def test_all_resources_are_owned(client):
    a, b = identity(client), identity(client)
    session = create(client, a)
    accepted = action(client, a, session['id'], 'start')
    sid, oid = session['id'], accepted['operation_id']
    for path in [f'/sessions/{sid}', f'/sessions/{sid}/messages', f'/sessions/{sid}/report', f'/operations/{oid}', f'/operations/{oid}/events']:
        assert client.get('/api/v1' + path, headers=b).status_code == 404
    assert client.post(f'/api/v1/operations/{oid}/cancel', headers=mutation(b)).status_code == 404
    assert client.get('/api/v1/sessions', headers=b).json()['data']['items'] == []


def test_busy_concurrency_and_terminal_is_unique(client):
    headers = identity(client)
    session = create(client, headers)
    client.app.state.runner.delay = 0.08
    def start(_):
        return client.post(f"/api/v1/sessions/{session['id']}/actions", headers=mutation(headers), json={'expected_version': 1, 'action': 'start'})
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(start, range(2)))
        assert sorted(r.status_code for r in results) == [202, 409]
        oid = next(r.json()['data']['operation_id'] for r in results if r.status_code == 202)
        wait(client, headers, oid)
        with client.app.state.session_factory() as db:
            assert db.scalar(select(func.count()).select_from(OperationEvent).where(OperationEvent.operation_id == uuid.UUID(oid),
                OperationEvent.event_type.in_(['operation.succeeded', 'operation.failed', 'operation.cancelled']))) == 1
    finally:
        client.app.state.runner.delay = 0.001


def test_pagination_abort_and_cascade_delete(client):
    headers = identity(client)
    first = create(client, headers)
    second = create(client, headers)
    listing = client.get('/api/v1/sessions?limit=1', headers=headers).json()['data']
    assert len(listing['items']) == 1 and listing['next_cursor']
    page2 = client.get('/api/v1/sessions', headers=headers, params={'limit': 1, 'cursor': listing['next_cursor']}).json()['data']
    assert listing['items'][0]['id'] != page2['items'][0]['id']
    assert client.get('/api/v1/sessions?cursor=invalid', headers=headers).status_code == 400
    action(client, headers, first['id'], 'abort')
    action(client, headers, second['id'], 'start')
    action(client, headers, second['id'], 'finish')
    current = get(client, headers, second['id'])
    deleted = client.delete(f"/api/v1/sessions/{second['id']}", headers=mutation(headers), params={'expected_version': current['version']})
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/sessions/{second['id']}", headers=headers).status_code == 404


@pytest.mark.parametrize('config', [{'question_count': 0}, {'question_count': 11}, {'max_followups': 3}, {'difficulty': True}, {'pressure_level': 4}])
def test_configuration_bounds(client, config):
    headers = identity(client)
    assert client.post('/api/v1/sessions', headers=mutation(headers), json={'config': config}).status_code == 422


def test_startup_recovers_a_persisted_running_operation(test_app):
    token = secrets.token_urlsafe(32)
    with test_app.state.engine.begin() as connection:
        connection.execute(text('TRUNCATE users CASCADE'))
    with test_app.state.session_factory() as db:
        user = User(display_name='启动恢复夹具', token_hash=hash_secret(token), creation_key_hash=hash_secret(secrets.token_hex(32)))
        db.add(user)
        db.flush()
        db.add(Profile(user_id=user.id))
        session = InterviewSession(user_id=user.id, title='未完成操作', role='frontend', mode='technical', status='ready',
            config={'question_count': 1, 'difficulty': 1, 'max_followups': 0, 'pressure_level': 1, 'pressure_consent': False}, version=2)
        db.add(session)
        db.flush()
        operation = Operation(user_id=user.id, session_id=session.id, kind='start', key_hash=hash_secret('interrupted'),
            request_payload={'expected_version': 1, 'action': 'start', 'question_id': None}, expected_session_version=2, status='running')
        db.add(operation)
        db.commit()
        oid, sid = str(operation.id), str(session.id)
    headers = {'Authorization': 'Bearer ' + token}
    with TestClient(test_app) as client:
        recovered = wait(client, headers, oid, 'failed')
        assert recovered['error_code'] == 'PROCESS_INTERRUPTED'
        assert get(client, headers, sid)['current_question'] is None
        assert client.post(f'/api/v1/operations/{oid}/retry', headers=mutation(headers)).status_code == 202
        wait(client, headers, oid)
        assert get(client, headers, sid)['current_question']['ordinal'] == 1
