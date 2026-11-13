"""Author reference + actual DeepSeek outputs; explicitly NOT two human reviewers."""
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
KEYS=['relevance','accuracy_consistency','reasoning','evidence_detail','communication']
# Authored reference judgements for these exact synthetic answers; not human ground truth.
REFERENCE={
 'technical-strong':([5,4.5,4.5,4,4.5], ['覆盖主流程与资源影响','主要概念准确，但简化了渲染树构建','解释缓存与阻塞的因果，内部机制可深化','给出可观察工具，但没有实际观测数据','顺序清楚且注明非全串行']),
 'technical-medium':([4,3.5,2.5,2,3.5], ['围绕主要流程作答','主要方向成立，解析到绘制的环节简略','只列步骤，未解释阻塞原因','没有具体页面或观测例子','表达简明，坦诚说明不确定']),
 'technical-weak':([2,0,0,0,3], ['提到页面显示但未回答流程','把网页当图片且否认解析，关键概念错误','错误前提，没有有效推导','没有支持题意的正确例子','句子清楚，表达清楚不等于技术正确']),
 'behavioral-strong':([4.5,4,4,4.5,4.5], ['按项目任务和行动结果作答','内部叙述一致，不核实案例真实性','复现问题后选择事务和条件更新','明确个人接口、并发测试与可观察结果','结构清楚，划定个人贡献范围']),
 'behavioral-medium':([4,3.5,3,2.5,3.5], ['围绕个人接口和项目','叙述可理解，未交代并发保证细节','从错误到用事务有路径，但取舍不充分','缺少并发验证结果，不能从演示推断正确性','大致顺序清楚但结果含糊']),
 'behavioral-weak':([2,2,1,1,2], ['涉及项目但未展开职责','没有明确矛盾，但也缺少可验证叙述','未说明问题、决策和行动因果','个人贡献、具体行动和结果均模糊','泛泛叙述，STAR 信息不足']),
 'pressure-strong':([5,4.5,4.5,4.5,4.5], ['直接选择一项贡献并给依据','结论与实验范围一致，没有推广到生产','说明时间约束、替代方案和取舍','库存为一、两请求的具体现象支持范围内结论','回应清楚且坦承边界，不评价心理状态']),
 'pressure-medium':([4,3.5,3,2,3.5], ['明确选择接口并说明核心性','承认缺数据，但事务保证说法仍笼统','理由较少，没有替代方案取舍','没有实验数据，论据不足','能说明限制，但缺少进一步验证计划']),
 'pressure-weak':([2,1,0,0,2], ['表达方案立场，未给题目要求的依据','无条件声称正确，没有支持','没有推理或约束分析','没有证据，并拒绝验证','句子可理解，但未建设性回应质疑']),
}


def main():
    samples=json.loads((ROOT/'tests/fixtures/m3-scoring-samples.json').read_text(encoding='utf-8'))['samples']
    stamp=datetime.now(timezone.utc).isoformat()
    a={'reviewer_id':'Codex-authored-reference','reviewer_type':'ai_assisted','reviewed_at':stamp,'rubric_version':'rubric-1.0','reviews':[]}
    b={'reviewer_id':'DeepSeek-actual-output','reviewer_type':'ai_assisted','reviewed_at':stamp,'rubric_version':'rubric-1.0','reviews':[]}
    errors={k:[] for k in KEYS};missing=[]; records=[]
    for i,sample in enumerate(samples,1):
        mid=sample['id'];opaque=f'S{i:02}'
        actual=json.loads((ROOT/f'.runtime/m3-sample-{mid}.json').read_text(encoding='utf-8'))
        evaluation=actual['results'][-1]['evaluation']
        scores,reasons=REFERENCE.get(mid,([None]*5,['没有实质知识或经历回答，无法据此推断该维能力；明确表示不会不自动等于各维零分。']*5))
        dims={};bdims={}
        for key,score,reason in zip(KEYS,scores,reasons):
            dims[key]={'status':'scored' if score is not None else 'insufficient','score':score,'reason':reason,
                       'quote':sample['answer'] if score is not None else ''}
            d=evaluation['dimensions'][key];other=float(d['score']) if d['score'] is not None else None
            bdims[key]={'status':'scored' if other is not None else 'insufficient','score':other,'reason':d['reason'],
                        'quote':d['evidence'][0]['quote'] if d['evidence'] else ''}
            assert not bdims[key]['quote'] or bdims[key]['quote'] in sample['answer']
            if score is not None and other is not None: errors[key].append(abs(score-other))
            elif (score is None)!=(other is None):missing.append({'sample_id':mid,'dimension':key,'reference':score,'model':other})
        a['reviews'].append({'sample_id':opaque,'dimensions':dims})
        b['reviews'].append({'sample_id':opaque,'dimensions':bdims})
        records.append({'sample_id':mid,'reference':dims,'deepseek':bdims,'model_run':{k:v for k,v in actual['results'][-1].items() if k!='evaluation'}})
    metric={k:{'paired_dimensions':len(v),'mean_absolute_difference':round(sum(v)/len(v),4) if v else None} for k,v in errors.items()}
    all_errors=[x for v in errors.values() for x in v]
    out={'evaluation_type':'model_assisted_not_human','human_reviewers':0,'independent_blind_review':False,
         'limitations':'Codex reference knows author sample design; model-to-model difference is not human MAE, reliability or fairness evidence.',
         'rubric_version':'rubric-1.0','reviewed_at':stamp,'per_dimension':metric,
         'paired_dimensions':len(all_errors),'mean_absolute_difference':round(sum(all_errors)/len(all_errors),4) if all_errors else None,
         'missingness_disagreements':missing,'samples':records}
    (ROOT/'tests/fixtures/m3-model-assisted-review.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    packet=ROOT/'.runtime/human-review';packet.mkdir(exist_ok=True,parents=True)
    for name,value in [('reviewer-A.json',a),('reviewer-B.json',b)]:
        path=packet/name
        if path.exists():
            old=json.loads(path.read_text(encoding='utf-8-sig') or '{}')
            if old.get('reviewer_id') and old.get('reviewer_type')!='ai_assisted':
                raise RuntimeError('Refusing to replace a real person review')
        path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    for alias in ('A','B'):
        path=packet/f'reviewer-{alias}.md'
        if path.exists():
            previous=path.read_text(encoding='utf-8')
            if not previous.startswith('# 当前为模型辅助评估'):
                path.write_text('# 当前为模型辅助评估，非真实人工盲评\n\n用户已取消人工填写。对应 JSON 已由 AI 填完：A 为 Codex 作者参照，B 为实际 DeepSeek 输出。人工人数为零，作者知道样本设计，不是独立盲评。下方保留原题和早期人工预案，仅供核对，不再要求人员填写。\n\n'+previous,encoding='utf-8')
    print(json.dumps({'samples':len(records),'human_reviewers':0,'paired_dimensions':len(all_errors),
                      'mean_absolute_difference':out['mean_absolute_difference'],'missingness_disagreements':len(missing)},ensure_ascii=False))


if __name__=='__main__':main()
