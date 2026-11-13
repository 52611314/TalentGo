from app.core.errors import AppError

ALLOWED = {
    'clarify': {'clarifying'}, 'clarification': {'clarifying'},
    'start': {'ready'}, 'answer': {'interviewing'}, 'hint': {'interviewing'},
    'skip': {'interviewing'}, 'pause': {'interviewing'}, 'resume': {'paused'},
    'lower_pressure': {'interviewing', 'paused'}, 'finish': {'interviewing', 'paused'},
    'abort': {'clarifying', 'ready'},
}
ACTIVE = {'queued', 'running'}
TERMINAL = {'succeeded', 'failed', 'cancelled'}


def require_action(state: str, action: str):
    if state not in ALLOWED.get(action, set()):
        raise AppError(409, 'INVALID_STATE', '当前面试状态不允许此操作', {'status': state, 'action': action})


def configuration_state(role, mode):
    return 'ready' if role and mode else 'clarifying'
