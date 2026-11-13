import json
from dataclasses import dataclass
from pathlib import Path

from app.schemas.evaluation import AnswerEvaluation, GeneratedHint, GeneratedQuestion
from app.services.scoring import validate_evidence

AGENT_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class InterviewSkill:
    key: str
    title: str
    trigger_mode: str
    version: str = '1.0'

    def triggered(self, context):
        return context['mode'] == self.trigger_mode and (self.key != 'pressure' or context['config']['pressure_consent'])

    def system(self):
        return (AGENT_DIR / 'prompts/system.md').read_text(encoding='utf-8') + '\n' + (AGENT_DIR / f'prompts/{self.key}.md').read_text(encoding='utf-8')

    def generate_question(self, provider, context, check):
        def validate(question):
            if question.topic != context['seed']['topic']:
                raise ValueError('Generated topic must match this question rubric')
            if question.question in context.get('previous_questions', []):
                raise ValueError('Do not repeat a main question')
        return provider.generate(GeneratedQuestion, self.system() + '\n根据题目种子与画像生成一个主问题，topic 必须等于 seed.topic。',
                                 context, check, validate)

    def evaluate(self, provider, context, check):
        prompt = (AGENT_DIR / 'prompts/evaluation.md').read_text(encoding='utf-8')
        return provider.generate(AnswerEvaluation, self.system() + '\n' + prompt, context, check,
                                 lambda value: validate_evidence(value, context['thread']))

    def hint(self, provider, context, check):
        return provider.generate(GeneratedHint, self.system() + '\n只提供一个简短提示帮助理解当前问题，不代写完整答案。', context, check)
