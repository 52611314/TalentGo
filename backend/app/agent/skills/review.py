from pathlib import Path
from app.agent.skills.base import AGENT_DIR
from app.schemas.evaluation import InterviewReview


class ReviewSkill:
    key, title, version = 'review', '证据复盘', '1.0'

    def triggered(self, context):
        return context.get('finishing', False)

    def review(self, provider, context, check):
        allowed = {str(e['question_id']) for e in context['evaluations']}
        def validate(value):
            for item in value.strengths + value.gaps + value.recommendations:
                if any(str(identifier) not in allowed for identifier in item.question_ids):
                    raise ValueError('Review references an unevaluated or foreign question')
        prompt = (AGENT_DIR / 'prompts/system.md').read_text(encoding='utf-8') + '\n' + (AGENT_DIR / 'prompts/review.md').read_text(encoding='utf-8')
        return provider.generate(InterviewReview, prompt, context, check, validate)
