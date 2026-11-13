import json
import pytest
from app.services.exporting import plain
from app.services.scoring import question_score
from app.schemas.evaluation import DIMENSIONS
from test_interview import action,answer,create,get,identity,mutation
from test_m3 import provider,real_session


@pytest.mark.parametrize('mode',['technical','behavioral','pressure'])
def test_only_clarity_and_relevance_never_produce_content_score(mode):
    dims={k:{'score':None} for k in DIMENSIONS}
    dims['relevance']['score']=5;dims['communication']['score']=5
    assert question_score(dims,mode) is None
    dims['reasoning']['score']=0
    assert question_score(dims,mode) is not None # Known poor reasoning is different from unknown.


@pytest.mark.parametrize('format',['markdown','json'])
def test_export_preserves_source_evidence_versions_and_ownership(client,provider,format):
    h=identity(client);sid=real_session(client,h)['id'];action(client,h,sid,'start');answer(client,h,sid,'<script>alert(1)</script> `\n```\n# 不可信标题\n[点击](javascript:alert(1))')
    response=client.get(f'/api/v1/sessions/{sid}/report/export?format={format}',headers=h)
    assert response.status_code==200 and 'attachment;' in response.headers['content-disposition']
    assert 'no-store' in response.headers['cache-control'] and 'nosniff' in response.headers['x-content-type-options']
    assert 'rubric-1.1' in response.text and 'prompt-1.2' in response.text
    if format=='json':
        data=response.json();assert data['is_mock'] is False and data['total_score']==80
        q=data['question_evaluations'][0];e=q['dimensions']['reasoning']['evidence'][0]
        assert e['quote'] in next(m for m in data['messages'] if m['id']==e['message_id'])['content']
        assert all(key not in data for key in ['token','llm_api_key','profile_snapshot','model_base_url'])
    else:assert '````text\n<script>' in response.text
    assert client.get(f'/api/v1/sessions/{sid}/report/export?format={format}',headers=identity(client)).status_code==404


def test_mock_export_and_not_ready_do_not_fabricate_score(client):
    h=identity(client);sid=create(client,h,config={'question_count':1})['id']
    assert client.get(f'/api/v1/sessions/{sid}/report/export',headers=h).status_code==409
    action(client,h,sid,'start');action(client,h,sid,'finish')
    response=client.get(f'/api/v1/sessions/{sid}/report/export?format=json',headers=h)
    assert response.json()['is_mock'] and response.json()['total_score'] is None
    assert client.get(f'/api/v1/sessions/{sid}/report/export?format=html',headers=h).status_code==422


def test_markdown_fence_always_at_least_three_and_longer_than_content():
    for value in ['hello','one ` tick','```\n<script>x</script>','`````']:
        text=plain(value);fence=text.split('text\n',1)[0]
        assert len(fence)>=3 and fence not in value and text.endswith(fence)


def test_operation_timings_are_measured_and_unknown_upstream_not_zero(client,provider):
    h=identity(client);sid=real_session(client,h)['id'];action(client,h,sid,'start');answer(client,h,sid,'明确的本题答案')
    state=get(client,h,sid);timing=state['latest_operation']['timings']
    assert 0<=timing['first_event_ms']<=timing['first_visible_text_ms']<=timing['completion_ms']
    trace=client.get(f'/api/v1/sessions/{sid}/trace',headers=h).json()['data']['items']
    assert all(t['usage']['upstream_first_content_ms'] is None for t in trace)


def test_old_task_stays_visible_but_cannot_start_under_new_rubric(client,test_app,provider):
    from app.models import PracticeTask
    from sqlalchemy import select
    h=identity(client);sid=real_session(client,h)['id'];action(client,h,sid,'start');answer(client,h,sid,'模糊')
    with test_app.state.session_factory() as db:
        row=db.scalar(select(PracticeTask));row.rubric_version='rubric-1.0';db.commit()
    task=client.get('/api/v1/practice-tasks',headers=h).json()['data']['items'][0]
    assert not task['can_practice'] and not task['version_supported']
    response=client.post('/api/v1/sessions',headers=mutation(h),json={'provider':'deepseek','role':'frontend','mode':'technical','source_task_id':task['id']})
    assert response.status_code==409 and response.json()['error']['code']=='TASK_VERSION_UNSUPPORTED'
