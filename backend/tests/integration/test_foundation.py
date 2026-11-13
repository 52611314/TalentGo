import secrets
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select, text

from app.core.security import hash_secret
from app.models import Profile, User


def create(client, name='M1 测试身份', key=None):
    return client.post('/api/v1/identity', json={'display_name': name},
                       headers={'Idempotency-Key': key or secrets.token_hex(32)})


def auth(identity, key=None):
    result = {'Authorization': 'Bearer ' + identity['token']}
    if key:
        result['Idempotency-Key'] = key
    return result


def test_health_and_real_database_port(client):
    assert client.get('/api/v1/health/live').json()['data']['milestone'] == 'M5'
    ready = client.get('/api/v1/health/ready')
    assert ready.status_code == 200
    assert ready.json()['data']['port'] == 6543
    with client.app.state.engine.connect() as connection:
        assert connection.execute(text('SHOW port')).scalar_one() == '6543'


def test_identity_creates_profile_without_storing_plaintext_token(client):
    result = create(client, '  开发者  ')
    assert result.status_code == 201
    data = result.json()['data']
    assert data['display_name'] == '开发者'
    assert data['profile']['user_id'] == data['user_id']
    assert data['profile']['allow_inferred_memory'] is False
    assert data['profile']['version'] == 1
    with client.app.state.session_factory() as db:
        user = db.scalar(select(User))
        assert user.token_hash == hash_secret(data['token'])
        assert user.token_hash != data['token']
    assert client.get('/api/v1/identity/me', headers=auth(data)).json()['data']['user_id'] == data['user_id']
    assert 'token' not in client.get('/api/v1/identity/me', headers=auth(data)).json()['data']


def test_creation_key_is_one_time_and_atomic(client):
    key = secrets.token_hex(32)
    assert create(client, key=key).status_code == 201
    repeated = create(client, key=key)
    assert repeated.status_code == 409
    assert repeated.json()['error']['code'] == 'IDENTITY_ALREADY_CREATED'
    assert 'token' not in repeated.text
    with client.app.state.engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM users')).scalar_one() == 1
        assert connection.execute(text('SELECT count(*) FROM profiles')).scalar_one() == 1


def test_bad_identity_requests_rejected_without_echoing_input(client):
    for body in [{'display_name': '   '}, {'display_name': 'x' * 61}, {'display_name': 'A', 'user_id': 'secret-user'}]:
        result = client.post('/api/v1/identity', json=body, headers={'Idempotency-Key': secrets.token_hex(32)})
        assert result.status_code == 422
        assert 'secret-user' not in result.text
    assert create(client, key='short').status_code == 422
    assert client.post('/api/v1/identity', json={'display_name': 'A'}).status_code == 422


def test_authentication_required_and_revoked_token_rejected(client):
    assert client.get('/api/v1/profile').status_code == 401
    assert client.get('/api/v1/profile', headers={'Authorization': 'Bearer wrong'}).status_code == 401
    data = create(client).json()['data']
    with client.app.state.session_factory() as db:
        db.scalar(select(User)).status = 'revoked'
        db.commit()
    result = client.get('/api/v1/profile', headers=auth(data))
    assert result.status_code == 401
    assert result.headers['www-authenticate'] == 'Bearer'


def test_profile_save_is_persistent_and_user_isolated(client):
    a = create(client, 'A').json()['data']
    b = create(client, 'B').json()['data']
    body = {'expected_version': 1, 'target_role': 'backend', 'tech_stack': ['Python', 'PostgreSQL'], 'goals': '练项目表达'}
    saved = client.patch('/api/v1/profile', json=body, headers=auth(a, secrets.token_hex(32)))
    assert saved.status_code == 200
    assert saved.json()['data']['version'] == 2
    loaded_a = client.get('/api/v1/profile', headers=auth(a)).json()['data']
    loaded_b = client.get('/api/v1/profile', headers=auth(b)).json()['data']
    assert loaded_a['goals'] == '练项目表达'
    assert loaded_b['target_role'] is None and loaded_b['goals'] == ''
    assert client.get('/api/v1/profile/' + a['profile']['id'], headers=auth(b)).status_code == 404
    assert client.patch('/api/v1/profile', json={**body, 'user_id': a['user_id']}, headers=auth(b, 'cross-user')).status_code == 422


def test_profile_same_key_replays_and_changed_body_conflicts(client):
    identity = create(client).json()['data']
    key = secrets.token_hex(16)
    body = {'expected_version': 1, 'goals': 'same request'}
    first = client.patch('/api/v1/profile', json=body, headers=auth(identity, key))
    second = client.patch('/api/v1/profile', json=body, headers=auth(identity, key))
    assert first.status_code == second.status_code == 200
    assert first.json()['data'] == second.json()['data']
    conflict = client.patch('/api/v1/profile', json={**body, 'goals': 'different'}, headers=auth(identity, key))
    assert conflict.status_code == 409 and conflict.json()['error']['code'] == 'IDEMPOTENCY_CONFLICT'
    assert client.get('/api/v1/profile', headers=auth(identity)).json()['data']['version'] == 2


def test_stale_version_does_not_overwrite(client):
    identity = create(client).json()['data']
    assert client.patch('/api/v1/profile', json={'expected_version': 1, 'goals': 'first'}, headers=auth(identity, 'first')).status_code == 200
    stale = client.patch('/api/v1/profile', json={'expected_version': 1, 'goals': 'stale'}, headers=auth(identity, 'second'))
    assert stale.status_code == 409
    assert stale.json()['error']['details']['current_version'] == 2
    assert client.get('/api/v1/profile', headers=auth(identity)).json()['data']['goals'] == 'first'


def test_concurrent_same_key_replays_once(client):
    identity = create(client).json()['data']
    body = {'expected_version': 1, 'goals': 'concurrent'}
    def save(_):
        return client.patch('/api/v1/profile', json=body, headers=auth(identity, 'concurrent-key'))
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(save, range(2)))
    assert [r.status_code for r in responses] == [200, 200]
    assert responses[0].json()['data'] == responses[1].json()['data']
    assert client.get('/api/v1/profile', headers=auth(identity)).json()['data']['version'] == 2


def test_concurrent_distinct_keys_allow_one_version_update(client):
    identity = create(client).json()['data']
    def save(index):
        return client.patch('/api/v1/profile', json={'expected_version': 1, 'goals': str(index)}, headers=auth(identity, f'key-{index}'))
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(save, range(2)))
    assert sorted(r.status_code for r in responses) == [200, 409]


def test_profile_validation_and_nullability(client):
    identity = create(client).json()['data']
    for payload in [{'goals': None}, {'tech_stack': ['x'] * 21}, {'tech_stack': [' ']}, {'goals': 'x' * 4001}, {'target_role': 'admin'}, {'feedback_style': None}, {'expected_version': True}]:
        result = client.patch('/api/v1/profile', json={'expected_version': 1, **payload}, headers=auth(identity, secrets.token_hex(16)))
        assert result.status_code == 422
    assert client.patch('/api/v1/profile', json={'expected_version': 1, 'target_role': None}, headers=auth(identity, 'nullable')).status_code == 200


def test_request_metadata_and_cors(client):
    result = client.get('/api/v1/health/live', headers={'Origin': 'http://localhost:5173'})
    assert result.headers['cache-control'] == 'no-store'
    assert result.headers['x-request-id'] == result.json()['request_id']
    assert result.headers['access-control-allow-origin'] == 'http://localhost:5173'
    blocked = client.get('/api/v1/health/live', headers={'Origin': 'https://untrusted.invalid'})
    assert 'access-control-allow-origin' not in blocked.headers


def test_readiness_fails_for_schema_mismatch(client):
    with client.app.state.engine.begin() as db:
        db.execute(text("UPDATE alembic_version SET version_num='wrong'"))
    try:
        result = client.get('/api/v1/health/ready')
        assert result.status_code == 503
        assert result.json()['error']['code'] == 'SCHEMA_NOT_READY'
        assert client.get('/api/v1/health/live').status_code == 200
    finally:
        with client.app.state.engine.begin() as db:
            db.execute(text("UPDATE alembic_version SET version_num='0004_m4_memory'"))
