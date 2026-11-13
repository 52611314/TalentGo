from app.agent.skills.technical import TechnicalSkill
from app.agent.skills.behavioral import BehavioralSkill
from app.agent.skills.pressure import PressureSkill
from app.agent.skills.review import ReviewSkill
from app.core.errors import AppError

SKILLS = {skill.key: skill for skill in [TechnicalSkill(), BehavioralSkill(), PressureSkill(), ReviewSkill()]}


def select_skill(context):
    key = 'review' if context.get('finishing') else context['mode']
    skill = SKILLS[key]
    if not skill.triggered(context):
        raise AppError(409, 'SKILL_TRIGGER_REJECTED', '当前上下文不满足 Skill 触发条件')
    return skill
