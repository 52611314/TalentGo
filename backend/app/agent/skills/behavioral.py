from app.agent.skills.base import InterviewSkill

class BehavioralSkill(InterviewSkill):
    def __init__(self):
        super().__init__('behavioral', 'STAR 行为表达', 'behavioral')
