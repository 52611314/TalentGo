"""30 acceptance scenarios. Fixture output validates engineering, never model quality."""
import json
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone

import httpx
import pytest
from app.core.errors import AppError
from app.llm.base import ModelResult
from app.llm.deepseek import DeepSeekProvider
from app.schemas.evaluation import DIMENSIONS
from test_interview import (action,answer,create,get,identity,mutation,wait,
    test_invalid_state_and_pressure_consent as check_consent,
    test_shared_idempotency_and_answer_replay as check_idempotency,
    test_busy_concurrency_and_terminal_is_unique as check_concurrency,
    test_process_interruption_recovery_does_not_generate_on_get as check_recovery,
    test_sse_replay_resume_and_invalid_cursor as check_sse)
from test_m3 import (provider,real_session,report,
    test_real_natural_clarification_and_model_status as check_clarification,
    test_cancellation_during_model_never_commits_candidate as check_cancel)
from test_m4 import (test_confirmed_memories_injected_across_sessions_with_actual_usage as check_across,
    test_memory_change_cancels_stale_generation_before_commit as check_correct,
    test_delete_invalidates_summary_and_never_reinjects as check_delete,
    test_inferred_memory_requires_opt_in_and_confirmation as check_inference)
from tests.unit.test_deepseek import settings as wire_settings,stream
from tests.unit.test_m4_context import test_budget_trims_history_then_memory_without_slicing_current as check_budget

ROOT=Path(__file__).resolve().parents[3]
CASES=[json.loads(line) for path in sorted((ROOT/'tests/scenarios').glob('*.jsonl')) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


@pytest.fixture(scope='module')
def records():
    rows=[]
    yield rows
    target=ROOT/'tests/results/m5-scenarios.json'
    target.parent.mkdir(exist_ok=True,parents=True)
    target.write_text(json.dumps({'suite':'m5-engineering','provider':'deterministic_fixture_not_live',
        'generated_at':datetime.now(timezone.utc).isoformat(),'api':'0.5.0','prompt':'prompt-1.2','rubric':'rubric-1.1',
        'catalog_count':len(CASES),'executed':len(rows),'cases':rows},ensure_ascii=False,indent=2),encoding='utf-8')


def dialogue(client,provider,case):
    h=identity(client)
    plans={t['content']:t for t in case['turns'] if t['action']=='answer'}
    original=provider.generate;contexts=[]
    def generate(schema,system,context,check,validate=None):
        contexts.append(context)
        if schema.__name__!='AnswerEvaluation':return original(schema,system,context,check,validate)
        check()
        source=[m for m in context['thread'] if m['speaker']=='user' and m['kind']=='answer'][-1]
        turn=plans[source['content']];score=turn['fixture_score'];flag=turn['fixture_flag']
        value=schema.model_validate({'dimensions':{k:{'score':score,'reason':'固定夹具验证：'+case['title'],
            'evidence':[{'message_id':source['id'],'quote':source['content']}] if score is not None else []} for k in DIMENSIONS},
            'flag':flag,'missing_points':['需补充当前题的依据'] if flag!='normal' else [],
            'suggestion':'针对当前题补充依据与边界。','followup':'请针对当前题补充一个具体依据。' if flag!='normal' else None})
        if validate:validate(value)
        return ModelResult(value,10,20,1,1)
    provider.generate=generate
    followups=int(len(plans)>1 or any(t['action']=='finish' for t in case['turns']))
    session=create(client,h,provider='deepseek',role=case['role'],mode=case['mode'],title=case['id'],
        config={'question_count':case['question_count'],'max_followups':followups,'pressure_consent':case['mode']=='pressure','pressure_level':3})
    sid=session['id'];action(client,h,sid,'start')
    qid=get(client,h,sid)['current_question']['id'];observed_followups=0;hint_used=False
    for turn in case['turns']:
        if turn['action']=='answer':answer(client,h,sid,turn['content'])
        else:action(client,h,sid,turn['action'],**{k:v for k,v in turn.items() if k=='pressure_level'})
        state=get(client,h,sid)
        if turn['action'] in ('pause','resume'):assert state['current_question']['id']==qid
        if state['current_question']:
            observed_followups=max(observed_followups,state['current_question']['followup_count'])
            hint_used=hint_used or state['current_question']['hint_used']
    result=report(client,h,sid);expected=case['expected']
    assert result['status']=='ready' and result['total_score']==expected['score']
    assert observed_followups==expected.get('followups',0)
    assert hint_used==expected.get('hint_used',False)
    for field in ('skipped','not_reached'):
        if field in expected:assert result['coverage'][field]==expected[field]
    assert len(result['question_evaluations'])<=1
    assert sum(m['kind']=='answer' for m in result['messages'])==len(plans)
    if 'pressure_level' in expected:
        assert get(client,h,sid)['config']['pressure_level']==expected['pressure_level']
        assert any(c.get('config',{}).get('pressure_level')==1 for c in contexts)
    return {'total_score':result['total_score'],'coverage':result['coverage'],'followups':observed_followups,
            'hint_used':hint_used,'timings':get(client,h,sid)['latest_operation']['timings']}


def fault_retry(client,provider,code):
    h=identity(client);sid=real_session(client,h)['id'];action(client,h,sid,'start');original=provider.generate
    def fail(*args,**kwargs):raise AppError(503,code,'受控上游故障')
    provider.generate=fail
    try:
        accepted,_=answer(client,h,sid,'故障前已保存的回答。',wait_for=False)
        assert wait(client,h,accepted['operation_id'],'failed')['error_code']==code
    finally:provider.generate=original
    r=client.post(f"/api/v1/operations/{accepted['operation_id']}/retry",headers=mutation(h),json={})
    assert r.status_code==202;wait(client,h,accepted['operation_id'])
    result=report(client,h,sid)
    assert len([m for m in result['messages'] if m['kind']=='answer'])==1


def wire_failure(client,provider,branch):
    h=identity(client);sid=real_session(client,h)['id'];action(client,h,sid,'start')
    original=client.app.state.runner.real.provider_factory;calls=[]
    def handler(request):
        calls.append(1)
        if branch=='stream_disconnect':raise httpx.ReadError('fixture disconnect')
        if branch=='bad_json':return stream('{bad json')
        source=json.loads(request.content)['messages'][1]['content']
        context=json.loads(source)['untrusted_material'];m=[m for m in context['thread'] if m['speaker']=='user'][-1]
        data={'dimensions':{k:{'score':5,'reason':'跨题伪造引用','evidence':[{'message_id':str(uuid.uuid4()),'quote':m['content']}]} for k in DIMENSIONS},
              'flag':'normal','missing_points':[],'suggestion':'伪造材料','followup':None}
        return stream(json.dumps(data,ensure_ascii=False))
    client.app.state.runner.real.provider_factory=lambda _:DeepSeekProvider(wire_settings(),transport=httpx.MockTransport(handler))
    try:
        accepted,_=answer(client,h,sid,'保留这条真实的本题答案。',wait_for=False)
        failed=wait(client,h,accepted['operation_id'],'failed')
        assert failed['error_code']==('MODEL_UNAVAILABLE' if branch=='stream_disconnect' else 'MODEL_OUTPUT_INVALID')
        assert get(client,h,sid)['coverage']['scored']==0
        assert len(calls)==(1 if branch=='stream_disconnect' else 2)
    finally:client.app.state.runner.real.provider_factory=original


@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_scenario(case,client,test_app,provider,records):
    row={'id':case['id'],'group':case['group'],'title':case['title'],'status':'failed','branches':[]}
    started=time.monotonic()
    try:
        if case['turns']:row['actual']=dialogue(client,provider,case)
        for check in case['engineering_checks']:
            if check=='pressure_consent':check_consent(client)
            elif check=='clarification':check_clarification(client,provider)
            elif check=='known_goal':
                h=identity(client);sid=real_session(client,h)['id'];action(client,h,sid,'start')
                assert 'ClarifiedGoal' not in provider.calls
            elif check=='memory_across':check_across(client,provider)
            elif check=='memory_correct':check_correct(client,provider)
            elif check=='memory_delete':check_delete(client,test_app,provider)
            elif check=='inference_off':check_inference(client,provider,False)
            elif check=='inference_confirm':check_inference(client,provider,True)
            elif check=='long_context':check_budget()
            elif check in ('timeout_retry','rate_retry'):fault_retry(client,provider,'MODEL_TIMEOUT' if check=='timeout_retry' else 'MODEL_RATE_LIMITED')
            elif check in ('bad_json','stream_disconnect','foreign_quote'):wire_failure(client,provider,check)
            elif check=='cancel':check_cancel(client,provider)
            elif check=='sse_replay':check_sse(client)
            elif check=='idempotency':check_idempotency(client)
            elif check=='concurrency':check_concurrency(client)
            elif check=='process_recovery':check_recovery(client)
            else:raise AssertionError('Unexecuted check '+check)
            row['branches'].append({'name':check,'status':'passed'})
        row['status']='passed'
    finally:
        row['elapsed_ms']=round((time.monotonic()-started)*1000)
        records.append(row)
