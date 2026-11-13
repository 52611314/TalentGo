import threading
import uuid
import pytest
from sqlalchemy import select
from app.agent.orchestrator import snapshot_for_model
from app.models import Memory, MemoryUsage, Profile, SessionSummary, InterviewSession, Operation, Report, PracticeTask
from app.agent.context_builder import build_context, seed_question
from test_interview import action, answer, create, get, identity, mutation, wait
from test_m3 import provider, real_session, report


def save_memory(client,h,**values):
    r=client.post('/api/v1/memories',headers=mutation(h),json={'kind':'preference','topic':'表达方式','content':'请先结论后举例',**values})
    assert r.status_code==201,r.text
    return r.json()['data']['id']


def listing(client,h): return client.get('/api/v1/memories',headers=h).json()['data']
def tasks(client,h): return client.get('/api/v1/practice-tasks',headers=h).json()['data']['items']
def latest_memory(client,h,mid): return next(m for m in listing(client,h)['items'] if m['id']==mid)


def profile_flag(client,h,enabled):
    p=client.get('/api/v1/profile',headers=h).json()['data']
    r=client.patch('/api/v1/profile',headers=mutation(h),json={'expected_version':p['version'],'allow_inferred_memory':enabled})
    assert r.status_code==200,r.text


def capture(provider):
    contexts=[]; original=provider.generate
    def generate(schema,system,context,check,validate=None):
        contexts.append((schema.__name__,context))
        return original(schema,system,context,check,validate)
    provider.generate=generate
    return contexts


def test_memory_crud_versions_replay_and_no_body_in_receipt(client):
    h=identity(client); key=mutation(h);body={'kind':'goal','topic':'网络','content':'SECRET_MEMORY_BODY'}
    first=client.post('/api/v1/memories',headers=key,json=body)
    replay=client.post('/api/v1/memories',headers=key,json=body)
    assert first.json()['data']==replay.json()['data']
    mid=first.json()['data']['id']; row=latest_memory(client,h,mid)
    assert row['confirmed'] and row['source_type']=='user_explicit'
    r=client.patch(f'/api/v1/memories/{mid}',headers=mutation(h),json={'expected_version':row['version'],'content':'修正目标'})
    assert r.status_code==200
    assert latest_memory(client,h,mid)['version']==2
    stale=client.delete(f'/api/v1/memories/{mid}?expected_version=1',headers=mutation(h))
    assert stale.status_code==409
    deleted=client.delete(f'/api/v1/memories/{mid}?expected_version=2',headers=mutation(h))
    assert deleted.status_code==200 and not listing(client,h)['items']
    replay=client.post('/api/v1/memories',headers=key,json=body)
    assert replay.status_code==201 and 'SECRET_MEMORY_BODY' not in replay.text
    assert not listing(client,h)['items']


def test_memory_isolation_and_validation(client):
    a=identity(client);b=identity(client);mid=save_memory(client,a)
    assert not listing(client,b)['items']
    for method,path,body in [('patch',f'/memories/{mid}',{'expected_version':1,'confirmed':True}),('delete',f'/memories/{mid}?expected_version=1',None)]:
        r=client.request(method,'/api/v1'+path,headers=mutation(b),json=body)
        assert r.status_code==404
    for content in (' ', 'x'*1201):
        r=client.post('/api/v1/memories',headers=mutation(a),json={'kind':'goal','topic':'目标','content':content})
        assert r.status_code==422


def test_confirmed_memories_injected_across_sessions_with_actual_usage(client,provider):
    h=identity(client);mid=save_memory(client,h); seen=capture(provider)
    for _ in range(2):
        sid=real_session(client,h)['id'];action(client,h,sid,'start');action(client,h,sid,'finish')
        usages=client.get(f'/api/v1/sessions/{sid}/memory-usages',headers=h).json()['data']['items']
        assert any(u['memory_id']==mid and u['phase']=='question' for u in usages)
        assert 'content' not in usages[0]
    contexts=[c for n,c in seen if n=='GeneratedQuestion']
    assert all(c['memories'][0]['content']=='请先结论后举例' for c in contexts)
    stranger=identity(client)
    assert client.get(f'/api/v1/sessions/{sid}/memory-usages',headers=stranger).status_code==404


def test_exact_topic_and_role_filter_and_no_other_identity(client,provider):
    h=identity(client);other=identity(client)
    save_memory(client,h,kind='weakness',topic='不相关主题',content='WRONG_TOPIC')
    save_memory(client,h,role='backend',content='WRONG_ROLE')
    save_memory(client,other,content='OTHER_USER')
    mid=save_memory(client,h,kind='weakness',topic='浏览器基础',role='frontend',mode='technical')
    seen=capture(provider);sid=real_session(client,h)['id'];action(client,h,sid,'start')
    context=next(c for n,c in seen if n=='GeneratedQuestion')
    assert [m['id'] for m in context['memories']]==[mid]


def test_memory_change_cancels_stale_generation_before_commit(client,provider):
    h=identity(client);mid=save_memory(client,h);sid=real_session(client,h)['id'];provider.block=True
    op=action(client,h,sid,'start',wait_for=False)['operation_id']
    assert provider.entered.wait(3)
    r=client.patch(f'/api/v1/memories/{mid}',headers=mutation(h),json={'expected_version':1,'content':'新的明确偏好'})
    assert r.status_code==200
    assert wait(client,h,op,'failed')['error_code']=='MEMORY_REVISION_CHANGED'
    assert get(client,h,sid)['current_question'] is None
    provider.block=False
    r=client.post(f'/api/v1/operations/{op}/retry',headers=mutation(h),json={});assert r.status_code==202
    wait(client,h,op)
    usage=client.get(f'/api/v1/sessions/{sid}/memory-usages',headers=h).json()['data']['items']
    assert usage[-1]['memory_version']==2 and usage[-1]['attempt_no']==2


def test_delete_invalidates_summary_and_never_reinjects(client,test_app,provider):
    h=identity(client);mid=save_memory(client,h);seen=capture(provider)
    sid=real_session(client,h,count=2)['id'];action(client,h,sid,'start');answer(client,h,sid,'明确回答与例子')
    with test_app.state.session_factory() as db:
        summary=db.scalar(select(SessionSummary).where(SessionSummary.session_id==uuid.UUID(sid)))
        assert summary.content['completed_topics'][0]['ordinal']==1
    client.delete(f'/api/v1/memories/{mid}?expected_version=1',headers=mutation(h))
    with test_app.state.session_factory() as db:
        assert db.scalar(select(SessionSummary).where(SessionSummary.session_id==uuid.UUID(sid))) is None
    action(client,h,sid,'hint')
    context=[c for n,c in seen if n=='GeneratedHint'][-1]
    assert not context['memories'] and not context['session_summary'] and context['thread']
    usages=client.get(f'/api/v1/sessions/{sid}/memory-usages',headers=h).json()['data']['items']
    assert usages and all(not u['still_exists'] for u in usages)


@pytest.mark.parametrize('enabled',[False,True])
def test_inferred_memory_requires_opt_in_and_confirmation(client,provider,enabled):
    h=identity(client);profile_flag(client,h,enabled);seen=capture(provider)
    sid=real_session(client,h)['id'];action(client,h,sid,'start');answer(client,h,sid,'模糊')
    rows=listing(client,h)['items']
    assert bool(rows)==enabled
    assert len(tasks(client,h))==1
    if not enabled:return
    row=rows[0];assert not row['confirmed'] and row['source_type']=='system_inferred'
    sid2=real_session(client,h)['id'];action(client,h,sid2,'start')
    assert not [c for n,c in seen if n=='GeneratedQuestion'][-1]['memories']
    client.patch(f"/api/v1/memories/{row['id']}",headers=mutation(h),json={'expected_version':row['version'],'confirmed':True})
    sid3=real_session(client,h)['id'];action(client,h,sid3,'start')
    assert [c for n,c in seen if n=='GeneratedQuestion'][-1]['memories']
    profile_flag(client,h,False)
    sid4=real_session(client,h)['id'];action(client,h,sid4,'start')
    assert not [c for n,c in seen if n=='GeneratedQuestion'][-1]['memories']


def test_explicit_weakness_never_overwritten_by_inference(client,provider):
    h=identity(client);profile_flag(client,h,True)
    mid=save_memory(client,h,kind='weakness',topic='浏览器基础',role='frontend',mode='technical',content='已确认的用户判断')
    sid=real_session(client,h)['id'];action(client,h,sid,'start');answer(client,h,sid,'模糊')
    assert len(listing(client,h)['items'])==1 and latest_memory(client,h,mid)['content']=='已确认的用户判断'


def test_task_completion_requires_effective_same_topic_answer(client,provider):
    h=identity(client);sid=real_session(client,h,count=2)['id'];action(client,h,sid,'start')
    answer(client,h,sid,'具体完整回答');answer(client,h,sid,'模糊')
    task=tasks(client,h)[0];assert task['topic']!='浏览器基础'
    seen=capture(provider)
    replay=real_session(client,h,count=2,source_task_id=task['id'])['id']
    assert tasks(client,h)[0]['status']=='in_progress'
    action(client,h,replay,'start')
    context=[c for n,c in seen if n=='GeneratedQuestion'][-1]
    assert context['seed']['topic']==task['topic']
    assert tasks(client,h)[0]['status']=='in_progress'
    answer(client,h,replay,'完整具体的复练答案')
    assert get(client,h,replay)['current_question']['topic']!=task['topic']
    assert next(t for t in tasks(client,h) if t['id']==task['id'])['status']=='in_progress'
    answer(client,h,replay,'另一个主题的具体回答')
    assert tasks(client,h)[0]['status']=='completed'


def test_skip_does_not_complete_task_and_source_deletion_cascades(client,provider):
    h=identity(client);profile_flag(client,h,True);sid=real_session(client,h)['id']
    action(client,h,sid,'start');answer(client,h,sid,'模糊');task=tasks(client,h)[0]
    replay=real_session(client,h,source_task_id=task['id'])['id'];action(client,h,replay,'start');action(client,h,replay,'skip')
    assert tasks(client,h)[0]['status']=='pending'
    v=get(client,h,sid)['version']
    assert client.delete(f'/api/v1/sessions/{sid}?expected_version={v}',headers=mutation(h)).status_code==204
    assert not tasks(client,h) and not listing(client,h)['items']
    assert get(client,h,replay)['source_task_id'] is None


def test_tasks_ownership_config_and_busy_guard(client,provider):
    h=identity(client);sid=real_session(client,h)['id'];action(client,h,sid,'start');answer(client,h,sid,'模糊');task=tasks(client,h)[0]
    stranger=identity(client)
    assert client.get('/api/v1/practice-tasks/'+task['id'],headers=stranger).status_code==404
    for body in [{'provider':'mock','role':'frontend','mode':'technical'}, {'provider':'deepseek','role':'backend','mode':'technical'}]:
        r=client.post('/api/v1/sessions',headers=mutation(h),json={**body,'source_task_id':task['id']})
        assert r.status_code==422
    real_session(client,h,source_task_id=task['id'])
    r=client.post('/api/v1/sessions',headers=mutation(h),json={'provider':'deepseek','role':'frontend','mode':'technical','source_task_id':task['id']})
    assert r.status_code==409 and r.json()['error']['code']=='TASK_IN_PROGRESS'


def test_trends_exclude_mock_null_and_separate_versions(client,test_app,provider):
    h=identity(client)
    for _ in range(2):
        sid=real_session(client,h)['id'];action(client,h,sid,'start');answer(client,h,sid,'具体回答')
    mock=create(client,h,config={'question_count':1})['id'];action(client,h,mock,'start');action(client,h,mock,'finish')
    with test_app.state.session_factory() as db:
        r=db.scalar(select(Report).where(Report.session_id==uuid.UUID(sid)));r.rubric_version='rubric-fixture-other';db.commit()
    result=client.get('/api/v1/reports/trends',headers=h).json()['data']
    assert len(result['groups'])==2 and sum(len(g['points']) for g in result['groups'])==2
    assert not client.get('/api/v1/reports/trends',headers=identity(client)).json()['data']['groups']
