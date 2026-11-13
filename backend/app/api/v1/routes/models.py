from fastapi import APIRouter, Request
from app.api.deps import CurrentUser, response
from app.agent.skill_registry import SKILLS

router = APIRouter(prefix='/models', tags=['models'])


@router.get('/status')
def status(user: CurrentUser, request: Request):
    settings = request.app.state.settings
    configured = bool(settings.llm_api_key and settings.llm_api_key.get_secret_value().strip())
    return response(request, {'default_provider': settings.llm_provider,
        'providers': [{'id': 'mock', 'available': True, 'model': None, 'description': '固定规则演示，不计能力分'},
                      {'id': 'deepseek', 'available': configured, 'model': settings.llm_model,
                       'description': '密钥已配置，实际调用时验证连接' if configured else '需配置后端本地 API Key'}],
        'skills': [{'key': s.key, 'title': s.title, 'version': s.version} for s in SKILLS.values()]})
