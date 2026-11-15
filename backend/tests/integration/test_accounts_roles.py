"""Account boundaries and role-aware orchestration with a controlled provider."""
from datetime import datetime, timedelta, timezone
import uuid
import pytest
from sqlalchemy import select
from app.core.roles import ROLES, role_plan
from app.core.security import hash_secret, verify_password
from app.models import AuthSession, User, Question, PracticeTask
from app.services.auth import seed_local_admin
from app.llm.base import ModelResult
from test_interview import action, answer, create, get, mutation
from test_m3 import provider, report


def register(client, username='student_one', password='test-pass-123'):
    result = client.post('/api/v1/auth/register', json={'username': username, 'password': password})
    assert result.status_code == 201, result.text
    return result.json()['data']


def headers(account):
    return {'Authorization': 'Bearer ' + account['token']}


def test_registration_persists_only_salted_password_and_hashed_session(client):
    account = register(client, 'Student_One')
    assert account['username'] == 'student_one'
    assert account['profile']['user_id'] == account['user_id']
    assert 'password' not in account and 'password_hash' not in account
    with client.app.state.session_factory() as db:
        user = db.get(User, uuid.UUID(account['user_id']))
        assert user.password_hash != 'test-pass-123'
        assert verify_password('test-pass-123', user.password_hash)
        session = db.scalar(select(AuthSession))
        assert session.token_hash == hash_secret(account['token'])
        assert user.token_hash != session.token_hash
    logged = client.post('/api/v1/auth/login', json={'username': 'STUDENT_ONE', 'password': 'test-pass-123'})
    assert logged.status_code == 200
    assert logged.json()['data']['user_id'] == account['user_id']
    assert logged.json()['data']['token'] != account['token']


def test_duplicate_and_invalid_credentials(client):
    register(client)
    duplicate = client.post('/api/v1/auth/register', json={'username': 'STUDENT_ONE', 'password': 'different-password'})
    assert duplicate.status_code == 409
    wrong = client.post('/api/v1/auth/login', json={'username': 'student_one', 'password': 'wrong-password'})
    unknown = client.post('/api/v1/auth/login', json={'username': 'missing', 'password': 'wrong-password'})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()['error'] == unknown.json()['error']
    assert 'wrong-password' not in wrong.text


@pytest.mark.parametrize('username,password', [('a','password'), ('has space','password'), ('中文','password'), ('a'*33,'password'), ('valid','short'), ('valid','x'*129)])
def test_credential_bounds(client, username, password):
    result = client.post('/api/v1/auth/register', json={'username': username, 'password': password})
    assert result.status_code == 422
    assert f'"{password}"' not in result.text


def test_logout_revokes_only_current_login_and_expiry_is_enforced(client):
    account = register(client)
    another = client.post('/api/v1/auth/login', json={'username':'student_one','password':'test-pass-123'}).json()['data']
    assert client.post('/api/v1/auth/logout', headers=headers(account)).status_code == 204
    assert client.get('/api/v1/profile', headers=headers(account)).status_code == 401
    assert client.get('/api/v1/profile', headers=headers(another)).status_code == 200
    with client.app.state.session_factory() as db:
        row = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_secret(another['token'])))
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert client.get('/api/v1/profile', headers=headers(another)).status_code == 401


def test_local_admin_seed_is_idempotent_and_never_resets_password(client):
    with client.app.state.session_factory() as db:
        seed_local_admin(db)
        first = db.scalar(select(User).where(User.username == 'admin'))
        original = first.password_hash
        seed_local_admin(db)
        assert db.scalar(select(User).where(User.username == 'admin')).password_hash == original
    login = client.post('/api/v1/auth/login', json={'username':'admin','password':'password'})
    assert login.status_code == 200
    with client.app.state.session_factory() as db:
        db.scalar(select(User).where(User.username == 'admin')).status = 'revoked'
        db.commit()
    assert client.post('/api/v1/auth/login', json={'username':'admin','password':'password'}).status_code == 401
    assert client.get('/api/v1/profile', headers=headers(login.json()['data'])).status_code == 401


def test_account_resources_are_isolated_and_survive_relogin(client):
    a, b = register(client), register(client, 'student_two')
    h = headers(a)
    session = create(client, h, role='ux', config={'question_count':1})
    assert client.get(f"/api/v1/sessions/{session['id']}", headers=headers(b)).status_code == 404
    assert client.get('/api/v1/sessions', headers=headers(b)).json()['data']['items'] == []
    client.post('/api/v1/auth/logout', headers=h)
    relogged = client.post('/api/v1/auth/login', json={'username':'student_one','password':'test-pass-123'}).json()['data']
    assert get(client, headers(relogged), session['id'])['role'] == 'ux'


def test_anonymous_creation_is_disabled_outside_test_environment(client, monkeypatch):
    monkeypatch.setattr(client.app.state.settings, 'app_env', 'development')
    response = client.post('/api/v1/identity', json={'display_name':'old'}, headers={'Idempotency-Key':'a'*64})
    assert response.status_code == 410


def test_role_catalog_search_and_all_roles_are_accepted(client):
    h = headers(register(client))
    catalog = client.get('/api/v1/roles').json()['data']
    assert catalog['total'] == len(catalog['items']) == 48
    assert len({r['id'] for r in catalog['items']}) == 48
    assert catalog['max_roles'] == 3
    assert any(r['id'] == 'llm_app' for r in client.get('/api/v1/roles?q=RAG').json()['data']['items'])
    assert all('测试' in ' '.join([r['label'], r['focus'], *r['aliases']]) for r in client.get('/api/v1/roles?q=测试').json()['data']['items'])
    assert client.get('/api/v1/roles?q=不存在的岗位xyz').json()['data']['items'] == []
    for item in catalog['items']:
        session = create(client, h, role=item['id'], config={'question_count':1})
        assert session['role'] == item['id']


@pytest.mark.parametrize('role,secondary,count', [('ux',['ux'],5), ('ux',['hardware','hardware'],5), ('ux',['hardware','iot','llm_app'],6), ('ux',['unknown'],5), ('ux',['hardware'],2), ('ux',['hardware','llm_app'],3), (None,['hardware'],5), ('unknown',[],5)])
def test_role_selection_rejects_duplicates_unknowns_and_insufficient_budget(client, role, secondary, count):
    h = headers(register(client))
    result = client.post('/api/v1/sessions', headers=mutation(h), json={'role':role,'mode':'technical', 'config':{'question_count':count,'secondary_roles':secondary}})
    assert result.status_code == 422


def test_patch_cannot_bypass_role_budget_validation(client):
    h = headers(register(client))
    session = create(client, h, role='ux', config={'question_count':5,'secondary_roles':['hardware','llm_app']})
    result = client.patch(f"/api/v1/sessions/{session['id']}", headers=mutation(h), json={'expected_version':session['version'],'config':{'question_count':2,'secondary_roles':['hardware','llm_app']}})
    assert result.status_code == 422
    assert get(client,h,session['id'])['config']['question_count'] == 5


def test_primary_always_has_more_questions_than_secondary():
    for secondary in (['hardware'], ['hardware','llm_app']):
        for count in range(len(secondary)+2,11):
            allocation = role_plan('ux',{'question_count':count,'secondary_roles':secondary})
            assert sum(item['question_count'] for item in allocation) == count
            assert all(0 < item['question_count'] < allocation[0]['question_count'] for item in allocation[1:])
    assert [p['question_count'] for p in role_plan('ux',{'question_count':5,'secondary_roles':['hardware','llm_app']})] == [3,1,1]


def test_mixed_roles_question_evaluation_memory_tasks_and_exports(client, provider):
    h = headers(register(client))
    contexts = []
    strong_answers = False
    original = provider.generate
    def generate(schema, system, context, check, validate=None):
        contexts.append((schema.__name__, context))
        if schema.__name__ == 'GeneratedQuestion':
            value = schema.model_validate({'topic':context['seed']['topic'],
                'question':f"作为{context['role_label']}，请说明{context['seed']['topic']}的一个实践案例。",
                'anchors':['说明与本题岗位相符的具体做法','解释验证方法与适用边界']})
            if validate: validate(value)
            return ModelResult(value,10,20,1,1)
        result = original(schema,system,context,check,validate)
        if schema.__name__ == 'AnswerEvaluation' and strong_answers:
            result.value.missing_points = ['补充验证边界']
        return result
    provider.generate = generate
    for role in ['ux','hardware','llm_app']:
        r = client.post('/api/v1/memories', headers=mutation(h), json={'kind':'preference','topic':role,'content':role+'专属偏好','role':role})
        assert r.status_code == 201
    session = create(client,h,role='ux',provider='deepseek',config={'question_count':4,'max_followups':0,'secondary_roles':['hardware','llm_app']})
    sid = session['id']
    action(client,h,sid,'start')
    expected = ['ux','ux','hardware','llm_app']
    for role in expected:
        current = get(client,h,sid)
        assert current['current_question']['role'] == role
        strong_answers = True
        answer(client,h,sid,'练习回答：说明做法、推理与例子。')
    result = report(client,h,sid)
    assert result['coverage']['scored'] == 4
    assert [q['role'] for q in result['question_evaluations']] == expected
    assert [p['question_count'] for p in result['role_plan']] == [2,1,1]
    for name, context in contexts:
        if name in {'GeneratedQuestion','AnswerEvaluation'}:
            assert all(m['role'] == context['role'] for m in context['memories'])
        if name == 'GeneratedQuestion':
            assert context['question'] is None and not context['thread']
    assert [c['config']['difficulty'] for name,c in contexts if name == 'GeneratedQuestion'] == [1,2,1,1]
    assert [c['role'] for name,c in contexts if name == 'AnswerEvaluation'] == expected
    review = next(c for name,c in contexts if name == 'InterviewReview')
    assert [item['role'] for item in review['evaluations']] == expected
    tasks = client.get('/api/v1/practice-tasks',headers=h).json()['data']['items']
    assert {task['role'] for task in tasks} == set(expected)
    for task in tasks:
        with client.app.state.session_factory() as db:
            row = db.get(PracticeTask,uuid.UUID(task['id']))
            assert row.seed['target_role'] == row.role and len(row.seed['anchors']) >= 2
    exported = client.get(f'/api/v1/sessions/{sid}/report/export?format=json', headers=h)
    assert exported.status_code == 200
    assert exported.json()['role_plan'] == result['role_plan']
    trends = client.get('/api/v1/reports/trends',headers=h).json()['data']['groups']
    assert trends[0]['secondary_roles'] == ['hardware','llm_app']
