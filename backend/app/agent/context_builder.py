import json
from pathlib import Path
from app.core.errors import AppError
from app.core.security import hash_secret

KNOWLEDGE = Path(__file__).resolve().parents[1] / 'knowledge'


def seed_question(role, mode, ordinal):
    path = KNOWLEDGE / ('question_banks/' + role + '.json' if mode == 'technical' else 'rubrics/' + mode + '.json')
    return json.loads(path.read_text(encoding='utf-8'))['questions'][ordinal - 1]


def answer_hash(question, thread):
    return hash_secret(json.dumps({'question_id': question['id'], 'hint_used': question['hint_used'],
        'answers': [{'id': m['id'], 'content': m['content']} for m in thread if m['speaker'] == 'user' and m['kind'] == 'answer']},
        sort_keys=True, ensure_ascii=False))


def build_context(snapshot, seed, budget):
    context = {'role': snapshot['role'], 'mode': snapshot['mode'], 'config': snapshot['config'],
        'profile': snapshot['profile_snapshot'], 'question': snapshot['question'], 'seed': seed,
        'thread': snapshot['thread'], 'previous_questions': snapshot['previous_questions'],
        'recent_history': list(snapshot['history'])}
    # Remove old complete messages first. Never slice the current answer or fabricate a summary.
    while context['recent_history'] and len(json.dumps(context, ensure_ascii=False)) > budget - 10000:
        context['recent_history'].pop(0)
    if len(json.dumps(context, ensure_ascii=False)) > budget - 8000:
        raise AppError(422, 'CONTEXT_TOO_LONG', '当前题完整材料过长，请缩短输入；没有截断后评分')
    return context
