"""Small, explicit paid evaluation of one fixed synthetic calibration sample."""
import argparse
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from app.agent.context_builder import seed_question
from app.agent.skill_registry import select_skill
from app.core.config import Settings
from app.llm.deepseek import DeepSeekProvider
from app.services.scoring import PROMPT_VERSION, RUBRIC_VERSION, question_score


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--sample', required=True)
    parser.add_argument('--repeat', type=int, choices=[1, 2, 3], default=1)
    args = parser.parse_args()
    if not args.live:
        parser.error('--live required: each repeat makes 1 model call, with at most 1 repair')
    samples = json.loads((ROOT / 'tests/fixtures/m3-scoring-samples.json').read_text(encoding='utf-8'))['samples']
    sample = next((s for s in samples if s['id'] == args.sample), None)
    if sample is None:
        parser.error('Unknown sample ID')
    settings = Settings()
    skill = select_skill({'mode': sample['mode'], 'config': {'pressure_consent': True}})
    mid = str(uuid.uuid5(uuid.NAMESPACE_URL, sample['id']))
    context = {'role': sample['role'], 'mode': sample['mode'], 'profile': {},
        'config': {'difficulty': 1, 'max_followups': 1, 'pressure_level': 1, 'pressure_consent': True},
        'question': {'content': sample['question'], 'hint_used': False, 'followup_count': 0},
        'seed': seed_question(sample['role'], sample['mode'], 1),
        'thread': [{'id': mid, 'speaker': 'user', 'kind': 'answer', 'content': sample['answer']}],
        'recent_history': [], 'previous_questions': []}
    results = []
    for i in range(args.repeat):
        result = skill.evaluate(DeepSeekProvider(settings), context, lambda: None)
        value = result.value.model_dump(mode='json')
        score = question_score(value['dimensions'], sample['mode'])
        record = {'repeat': i + 1, 'score': float(score) if score is not None else None,
                  'evaluation': value, 'input_tokens': result.input_tokens, 'output_tokens': result.output_tokens,
                  'latency_ms': result.latency_ms, 'attempts': result.attempts}
        results.append(record)
        print(json.dumps({k: v for k, v in record.items() if k != 'evaluation'}, ensure_ascii=False), flush=True)
    output = {'sample_id': sample['id'], 'model': settings.llm_model, 'rubric_version': RUBRIC_VERSION,
              'prompt_version': PROMPT_VERSION, 'human_review_status': 'pending', 'results': results}
    runtime = ROOT / '.runtime'
    runtime.mkdir(exist_ok=True)
    (runtime / f'm3-sample-{sample["id"]}.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
