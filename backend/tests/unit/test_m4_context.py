import json
from pathlib import Path
from app.agent.context_builder import build_context, answer_hash


def snapshot():
    return {'role':'frontend','mode':'technical','config':{},'profile_snapshot':{},'question':{},
            'thread':[{'id':'current','content':'完整当前答案'}],'history':[],'previous_questions':[],
            'session_summary':{'completed_topics':[{'topic':'已完成主题','score':40}]}}


def memory(mid,source='user_explicit',kind='preference',topic='表达方式',content='反馈偏好'):
    return {'id':mid,'source_type':source,'kind':kind,'topic':topic,'content':content}


def test_context_conflicts_prefer_explicit_and_bound_to_eight():
    s=snapshot();s['memories']=[memory('inferred','system_inferred'),memory('explicit')]+[memory(str(i),topic=f'topic-{i}') for i in range(20)]
    c=build_context(s,{'topic':'浏览器基础'},48000)
    assert len(c['memories'])==8
    assert any(m['id']=='explicit' for m in c['memories']) and not any(m['id']=='inferred' for m in c['memories'])


def test_budget_trims_history_then_memory_without_slicing_current():
    s=snapshot();s['thread']=[{'content':'完整答案'*1200}];s['history']=[{'content':'旧资料'*6000}]
    s['memories']=[memory(str(i),topic=f'topic-{i}',content='偏好'*600) for i in range(8)]
    c=build_context(s,{'topic':'浏览器基础'},20000)
    assert c['thread']==s['thread'] and not c['recent_history'] and len(c['memories'])<8


def test_revision_changes_answer_cache_key():
    q={'id':'same-question','hint_used':False,'memory_revision':1}
    assert answer_hash(q,[])!=answer_hash({**q,'memory_revision':2},[])


def test_assisted_review_is_complete_and_explicitly_not_human():
    root=Path(__file__).resolve().parents[3]
    data=json.loads((root/'tests/fixtures/m3-model-assisted-review.json').read_text(encoding='utf-8'))
    source={s['id']:s for s in json.loads((root/'tests/fixtures/m3-scoring-samples.json').read_text(encoding='utf-8'))['samples']}
    assert data['human_reviewers']==0 and data['independent_blind_review'] is False
    assert len(data['samples'])==13
    for sample in data['samples']:
        for channel in ('reference','deepseek'):
            assert len(sample[channel])==5
            for dim in sample[channel].values():
                assert dim['status'] in ('scored','insufficient') and dim['reason']
                if dim['score'] is not None: assert 0<=dim['score']<=5 and dim['quote'] in source[sample['sample_id']]['answer']
