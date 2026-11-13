from fastapi import APIRouter, Request

from app.api.deps import CurrentUser, DB, Key, response
from app.core.errors import AppError
from app.schemas.identity import IdentityCreate
from app.services.identity import create_identity

router = APIRouter(prefix='/identity', tags=['identity'])


@router.post('', status_code=201)
def create(body: IdentityCreate, db: DB, key: Key, request: Request):
    if len(key) < 43:
        raise AppError(422, 'VALIDATION_ERROR', '身份创建请求键至少为 43 个随机字符')
    return response(request, create_identity(db, body.display_name, key))


@router.get('/me')
def me(user: CurrentUser, request: Request):
    return response(request, {'user_id': str(user.id), 'display_name': user.display_name, 'status': user.status})
