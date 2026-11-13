from app.agent.skills.base import InterviewSkill

class TechnicalSkill(InterviewSkill):
    def __init__(self):
        super().__init__('technical', '技术深挖', 'technical')
