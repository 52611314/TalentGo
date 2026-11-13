from app.agent.skills.base import InterviewSkill

class PressureSkill(InterviewSkill):
    def __init__(self):
        super().__init__('pressure', '建设性压力追问', 'pressure')
