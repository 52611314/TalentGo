import json
from pathlib import Path
from app.core.errors import AppError
from app.core.security import hash_secret
from app.core.roles import ROLE_BY_ID

KNOWLEDGE = Path(__file__).resolve().parents[1] / 'knowledge'


def seed_question(role, mode, ordinal):
    target = ROLE_BY_ID[role]
    if mode != 'technical' or role in {'frontend', 'backend'}:
        path = KNOWLEDGE / ('question_banks/' + role + '.json' if mode == 'technical' else 'rubrics/' + mode + '.json')
        seed = json.loads(path.read_text(encoding='utf-8'))['questions'][ordinal - 1]
    else:
        themes = ['核心概念与实践', '方案设计与取舍', '问题定位与验证', '质量与可靠性', '性能与成本',
                  '边界与风险', '协作与交付', '工具与工作流程', '复杂场景分析', '项目复盘与改进']
        seed = {'source_key': f'{role}-{ordinal:02}', 'topic': themes[ordinal - 1], 'dynamic': True,
            'question': f'请针对{target["label"]}，围绕{target["focus"]}中的一个具体能力点设计问题。主题：{themes[ordinal - 1]}。',
            'anchors': ['评价当前具体问题中的概念准确性、推理依据、实践验证与适用边界，不按关键词数量计分'],
            'boundary': '依据岗位工作范围与当前题目评价；不要求候选人掌握其他岗位全部技能，不虚构标准答案或经历。'}
    return {**seed, 'target_role': role, 'role_label': target['label'], 'role_focus': target['focus']}


def answer_hash(question, thread):
    return hash_secret(json.dumps({'question_id': question['id'], 'hint_used': question['hint_used'], 'memory_revision': question.get('memory_revision'),
        'answers': [{'id': m['id'], 'content': m['content']} for m in thread if m['speaker'] == 'user' and m['kind'] == 'answer']},
        sort_keys=True, ensure_ascii=False))


def build_context(snapshot, seed, budget):
    target_role = seed.get('target_role', snapshot['role'])
    context = {'role': target_role, 'role_label': ROLE_BY_ID[target_role]['label'], 'role_focus': ROLE_BY_ID[target_role]['focus'],
        'mode': snapshot['mode'], 'config': snapshot['config'],
        'profile': snapshot['profile_snapshot'], 'question': snapshot['question'], 'seed': seed,
        'thread': snapshot['thread'], 'previous_questions': snapshot['previous_questions'],
        'recent_history': list(snapshot['history'])}
    candidates = [m for m in snapshot.get('memories', []) if m.get('role') in (None, target_role)
                  and (m['kind'] != 'weakness' or m['topic'] == seed['topic'])]
    candidates.sort(key=lambda m: (m['topic'] != seed['topic'], m['source_type'] != 'user_explicit'))
    selected, seen = [], set()
    for item in candidates:
        key = (item['kind'], item['topic'])
        if key in seen: continue
        seen.add(key)
        selected.append(item)
        if len(selected) == 8: break
    context['memories'] = selected
    context['session_summary'] = snapshot.get('session_summary', {})
    context['practice_focus'] = snapshot.get('practice_focus')
    # Remove old complete messages first. Never slice the current answer or fabricate a summary.
    while context['recent_history'] and len(json.dumps(context, ensure_ascii=False)) > budget - 10000:
        context['recent_history'].pop(0)
    while context['memories'] and len(json.dumps(context, ensure_ascii=False)) > budget - 10000:
        context['memories'].pop()
    if len(json.dumps(context, ensure_ascii=False)) > budget - 10000:
        context['session_summary'] = {}
    if len(json.dumps(context, ensure_ascii=False)) > budget - 8000:
        raise AppError(422, 'CONTEXT_TOO_LONG', '当前题完整材料过长，请缩短输入；没有截断后评分')
    return context
