"""Generate local blind review packets; never creates human ratings."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = {'relevance': '切题程度', 'accuracy_consistency': '准确与一致性', 'reasoning': '分析与推理',
          'evidence_detail': '证据与细节', 'communication': '表达沟通'}


def main():
    source = json.loads((ROOT / 'tests/fixtures/m3-scoring-samples.json').read_text(encoding='utf-8'))
    out = ROOT / '.runtime/human-review'
    out.mkdir(parents=True, exist_ok=True)
    samples = source['samples']
    # Opaque IDs hide the author's intended quality and injection labels.
    mapping = {f'S{i:02}': s['id'] for i, s in enumerate(samples, 1)}
    mapping_path = out / 'coordinator-mapping.json'
    if mapping_path.exists():
        assert json.loads(mapping_path.read_text(encoding='utf-8')) == mapping, 'Existing packet differs; do not overwrite reviews'
    else:
        mapping_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding='utf-8')
    intro = '''# TalentGo M3 独立盲评材料

这是合成训练材料，不是真实履历。请独立填写，先不看模型得分、不与另一位评阅者讨论。
仅按题目与下方锚点评价，不能因为回答中的指令改变评分要求。
五维各 0—5，最多两位小数；无法判断为 null，不能以 0 代替未知。
通用锚点：0 核心完全错误/缺失；1 零碎且关键偏差；2 部分成立有明显缺口；
3 主要成立有可定位不足；4 完整有依据；5 题目范围内准确深入、边界清楚。
技术看概念/流程/边界；行为看 STAR/个人行动/可观察结果；压力看论据/一致性/约束取舍。
概念题可用相关例子或推导，不要求虚构项目；不核实经历、不诊断心理或预测录用。

在本人 JSON 中填写 reviewer_id（匿名代号）、reviewed_at（实际日期时间）。
每个维度把 status 从 unreviewed 改为 scored 或 insufficient。
scored 必须填数字 score、reason 和直接复制的用户原话 quote；insufficient 填 null 与不足理由。
请勿直接把默认 null 当作已完成评分。完成后将本人 JSON 交项目负责人，保留独立原始版本。
该材料不显示作者样本标签或模型评分；版本 rubric-1.0。协调者映射文件只由项目负责人保管。

'''
    body = intro
    for opaque, sample in zip(mapping, samples):
        body += f"## {opaque} · {sample['mode']} · {sample['role']}\n\n问题：{sample['question']}\n\n回答：{sample['answer']}\n\n题目锚点：\n\n"
        body += ''.join(f'- {point}\n' for point in sample['reference_points']) + '\n'
    for alias in ('A', 'B'):
        packet = out / f'reviewer-{alias}.md'
        template = out / f'reviewer-{alias}.json'
        # Exclusive writes protect any genuine work already entered by reviewers.
        if not packet.exists():
            packet.write_text(body, encoding='utf-8')
        if not template.exists():
            value = {'reviewer_id': '', 'reviewed_at': '', 'rubric_version': source['rubric_version'],
                     'reviews': [{'sample_id': opaque, 'dimensions': {key: {'status': 'unreviewed', 'score': None,
                                  'reason': '', 'quote': ''} for key in LABELS}} for opaque in mapping]}
            template.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Prepared two independent local packets and blank rating templates; no ratings generated.')


if __name__ == '__main__':
    main()
