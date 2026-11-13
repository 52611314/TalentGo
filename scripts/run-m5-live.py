"""Explicit paid M5 subset: 10 semantic cases + 3 local API one-question flows.

No humans are simulated. Original inputs are synthetic, selected IDs fixed before execution.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import secrets
import sys
import time
import uuid
from urllib.parse import urlsplit

import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.agent.context_builder import seed_question
from app.agent.skill_registry import select_skill
from app.core.config import Settings
from app.core.errors import AppError
from app.llm.deepseek import DeepSeekProvider
from app.services.scoring import RUBRIC_VERSION,PROMPT_VERSION,question_score


def usage(result):
    return {'input_tokens':result.input_tokens,'output_tokens':result.output_tokens,
        'input_cache_hit_tokens':result.input_cache_hit_tokens,'input_cache_miss_tokens':result.input_cache_miss_tokens,
        'upstream_first_content_ms':result.first_content_ms,'completion_ms':result.latency_ms,'attempts':result.attempts}


def cost_bounds(u,settings):
    # Public Flash USD rates verified 2026-11-13. Range avoids guessing peak/holiday/account billing.
    if settings.llm_model!='deepseek-flash' or urlsplit(settings.llm_base_url).hostname!='api.deepseek.com':return None
    if any(u.get(k) is None for k in ('input_cache_hit_tokens','input_cache_miss_tokens','output_tokens')):return None
    low=(u['input_cache_hit_tokens']*.003+u['input_cache_miss_tokens']*.15+u['output_tokens']*.6)/1_000_000
    return {'currency':'USD','off_peak_estimate':round(low,8),'peak_estimate':round(low*2,8),
        'rates_source':'https://api-docs.deepseek.com/quick_start/pricing/','verified_on':'2026-11-13','not_account_bill':True}


def semantic_case(case,settings):
    source=next(t for t in case['turns'] if t['action']=='answer')['content']
    seed=seed_question(case['role'],case['mode'],1)
    mid=str(uuid.uuid5(uuid.NAMESPACE_URL,'talentgo-m5-'+case['id']))
    context={'role':case['role'],'mode':case['mode'],'profile':{},
        'config':{'difficulty':1,'max_followups':1,'pressure_consent':True,'pressure_level':1},
        'seed':seed,'question':{'content':seed['question'],'hint_used':False,'followup_count':0},
        'thread':[{'id':mid,'speaker':'user','kind':'answer','content':source}],
        'memories':[],'session_summary':{},'recent_history':[],'previous_questions':[]}
    result=select_skill({'mode':case['mode'],'config':context['config']}).evaluate(DeepSeekProvider(settings),context,lambda:None)
    value=result.value.model_dump(mode='json');dims=value['dimensions']
    total=question_score(dims,case['mode'])
    score=lambda key:float(dims[key]['score']) if dims[key]['score'] is not None else None
    checks=['schema','same_answer_exact_quotes','server_score']
    if case['id']=='T01':assert score('accuracy_consistency') is not None and score('accuracy_consistency')>=3;checks.append('correct_content_not_low')
    if case['id'] in ('T02','H05'):assert score('accuracy_consistency') is None or score('accuracy_consistency')<=2.5;checks.append('known_error_not_high')
    if case['id']=='T04':
        assert all(dims[k]['score'] is None for k in ('accuracy_consistency','reasoning','evidence_detail')) and total is None
        checks.append('no_content_no_total')
    if case['id']=='T05':assert score('relevance') is None or score('relevance')<=2;checks.append('off_topic_not_relevant')
    if case['id'] in ('T03','H02','H05'):assert value['missing_points'];checks.append('missing_points_present')
    if case['id']=='T08':assert total is None or total<100;checks.append('injection_no_forced_full_score')
    if case['id']=='H01':assert score('evidence_detail') is not None and score('evidence_detail')>=3;checks.append('star_details_recognized')
    u=usage(result)
    return {'id':case['id'],'group':case['group'],'status':'passed','provider':'live_deepseek',
        'input':source,'evaluation':value,'total_score':float(total) if total is not None else None,
        'checks':checks,'usage':u,'cost_bounds':cost_bounds(u,settings)}


def api_flows(settings,role='frontend'):
    import runpy
    answers=runpy.run_path(str(ROOT/'scripts/smoke-model.py'))['ANSWERS']
    if role=='backend':
        answers={'technical':'合成案例：事务把相关的多步修改作为一个整体提交或回滚。以账户转账为例，扣款与入账都成功才提交，否则回滚，防止只扣不加。原子性保证整体成功或失败；隔离性处理并发事务相互影响，但不同隔离级别仍有不同异常，不能说事务自动解决所有并发问题。还需账户余额等业务约束，持久性依靠数据库日志等机制。'}
    records=[]
    with httpx.Client(base_url='http://127.0.0.1:8000/api/v1',trust_env=False,timeout=15) as client:
        def request(method,path,body=None,auth=None):
            headers={**(auth or {})}
            if method=='POST':headers['Idempotency-Key']=secrets.token_hex(32)
            r=client.request(method,path,json=body,headers=headers)
            if r.status_code>=400:raise RuntimeError(r.json().get('error',{}).get('code','HTTP_ERROR'))
            return r.json()['data']
        user=request('POST','/identity',{'display_name':'M5 合成场景与时延验证'})
        auth={'Authorization':'Bearer '+user['token']}
        def wait(oid):
            deadline=time.monotonic()+190
            while time.monotonic()<deadline:
                r=request('GET','/operations/'+oid,auth=auth)
                if r['status'] in ('succeeded','failed','cancelled'):
                    if r['status']!='succeeded':raise RuntimeError(r['error_code'] or r['status'])
                    return r
                time.sleep(.3)
            raise RuntimeError('LIVE_WAIT_TIMEOUT')
        for mode,text in answers.items():
            started=time.monotonic();sid=None
            try:
                state=request('POST','/sessions',{'title':'M5 合成闭环 · '+role+' · '+mode,'provider':'deepseek','role':role,'mode':mode,
                    'config':{'question_count':1,'max_followups':0,'pressure_consent':mode=='pressure'}},auth)
                sid=state['id'];first=wait(request('POST',f'/sessions/{sid}/actions',{'action':'start','expected_version':state['version']},auth)['operation_id'])
                state=request('GET',f'/sessions/{sid}',auth=auth)
                assert state['role']==role and state['mode']==mode
                last=wait(request('POST',f'/sessions/{sid}/messages',{'kind':'answer','question_id':state['current_question']['id'],
                    'content':text,'expected_version':state['version']},auth)['operation_id'])
                report=request('GET',f'/sessions/{sid}/report',auth=auth)
                assert report['status']=='ready' and not report['is_mock'] and report['coverage']['scored']==1
                assert report['rubric_version']==RUBRIC_VERSION and report['prompt_version']==PROMPT_VERSION
                trace=request('GET',f'/sessions/{sid}/trace',auth=auth)['items']
                for format in ('json','markdown'):
                    exported=client.get(f'/sessions/{sid}/report/export?format={format}',headers=auth)
                    assert exported.status_code==200 and RUBRIC_VERSION in exported.text
                records.append({'mode':mode,'role':role,'session_id':sid,'status':'passed','coverage':report['coverage'],
                    'total_score':report['total_score'],'model_trace':trace,'first_operation':first['timings'],
                    'last_operation':last['timings'],'elapsed_ms':round((time.monotonic()-started)*1000)})
            except Exception as error:records.append({'mode':mode,'session_id':sid,'status':'failed','error':str(error) if isinstance(error,RuntimeError) else type(error).__name__})
            print('api',mode,records[-1]['status'],flush=True)
    return records


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--live',action='store_true')
    parser.add_argument('--include-backend',action='store_true',help='Add one backend-role flow, about 3 extra model requests')
    args=parser.parse_args()
    if not args.live:parser.error('--live required; 10 evaluation requests plus about 9 API model requests, each at most one repair')
    settings=Settings();started=datetime.now(timezone.utc).isoformat()
    cases=[json.loads(line) for p in sorted((ROOT/'tests/scenarios').glob('*.jsonl')) for line in p.read_text(encoding='utf-8').splitlines() if line.strip()]
    results=[]
    for case in [c for c in cases if c['live_selected']]:
        try:row=semantic_case(case,settings)
        except Exception as e:row={'id':case['id'],'status':'failed','error':e.code if isinstance(e,AppError) else type(e).__name__}
        results.append(row);print(case['id'],row['status'],flush=True)
    try:
        flows=api_flows(settings)
        if args.include_backend:flows+=api_flows(settings,role='backend')
    except Exception as e:flows=[{'status':'failed','error':str(e) if isinstance(e,RuntimeError) else type(e).__name__}]
    data={'suite':'m5-live-subset','started_at':started,'model':settings.llm_model,'prompt':PROMPT_VERSION,'rubric':RUBRIC_VERSION,
        'human_reviewers':0,'provider':'real_deepseek','cases':results,'api_flows':flows,
        'limitations':'10 selected synthetic semantic cases and 3 synthetic API flows; not all 30 live, no human quality/learning-effect claim. No p50/p95 from this small heterogeneous sample.'}
    out=ROOT/'tests/results/m5-live.json';out.parent.mkdir(exist_ok=True,parents=True);out.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    if any(r['status']!='passed' for r in results+flows):raise SystemExit(1)


if __name__=='__main__':main()
