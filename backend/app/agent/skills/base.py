import re
from dataclasses import dataclass
from pathlib import Path

from app.schemas.evaluation import AnswerEvaluation, GeneratedHint, GeneratedQuestion
from app.services.scoring import validate_evidence

AGENT_DIR = Path(__file__).resolve().parents[1]
COMPOUND_REQUEST = re.compile(
    r'[；;]|[。！？?]\s*\S'
    r'|(?:什么|如何|怎样)[^。？！?]{0,30}[、，][^。？！?]{0,16}(?:什么|如何|怎样)'
    r'|[、，](?:并|再)(?:说明|解释|列出|给出|描述|补充)'
    r'|(?:说明|阐述)[^。？！?]{0,20}(?:目标和|原因和|过程和|目标、|行动、)'
)


def validate_single_question(question: str, limit: int):
    if len(question) > limit or '\n' in question or COMPOUND_REQUEST.search(question):
        raise ValueError(f'Ask one concrete point in one line within {limit} characters. Move separate requests to follow-ups.')


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
            if context['seed'].get('dynamic') and len(question.anchors) < 2:
                raise ValueError('Provide at least two question-specific evaluation anchors')
            validate_single_question(question.question, 110)
        return provider.generate(GeneratedQuestion, self.system() + '\n根据当前 role_label、role_focus、能力方向与画像实时生成一个岗位相关的主问题，topic 必须等于 seed.topic。'
                                 '问题单独一行，最多110字符，只有一个请求，最多一个问号，不列子任务。难度1只问基础概念或一个具体例子；'
                                 '行为题只问一个个人行动或一个结果，背景只在开头短语中给出。禁止同时要求交代目标和行动；'
                                 '其他细节留给追问。示例：“团队对车载网络方案有分歧时，你做了什么来推动合作？”允许课程、团队练习或实习例子。'
                                 'anchors 写2—3条简短本题评价要点，每条约25字，不扩大本题要求。',
                                 context, check, validate)

    def evaluate(self, provider, context, check):
        prompt = (AGENT_DIR / 'prompts/evaluation.md').read_text(encoding='utf-8')
        def validate(value):
            validate_evidence(value, context['thread'])
            if value.followup:
                validate_single_question(value.followup, 80)
        return provider.generate(AnswerEvaluation, self.system() + '\n' + prompt, context, check, validate)

    def hint(self, provider, context, check):
        return provider.generate(GeneratedHint, self.system() + '\n只提供一个简短提示帮助理解当前问题，不代写完整答案。', context, check)
