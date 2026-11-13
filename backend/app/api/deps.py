import re
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import hash_secret
from app.models import User
from app.repositories.users import find_active_user

bearer = HTTPBearer(auto_error=False)


def get_db(request: Request):
    with request.app.state.session_factory() as db:
        yield db


DB = Annotated[Session, Depends(get_db)]


def current_user(db: DB, credential: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> User:
    if credential is None or len(credential.credentials) > 128:
        raise AppError(401, 'INVALID_IDENTITY', '请先创建或切换训练身份')
    user = find_active_user(db, hash_secret(credential.credentials))
    if user is None:
        raise AppError(401, 'INVALID_IDENTITY', '训练身份无效，请检查本机保存的身份')
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def idempotency_key(value: Annotated[str, Header(alias='Idempotency-Key', min_length=1, max_length=80)]) -> str:
    if not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise AppError(422, 'VALIDATION_ERROR', '请求键只允许字母、数字、下划线和短横线')
    return value


Key = Annotated[str, Depends(idempotency_key)]


def response(request: Request, data) -> dict:
    return {'data': data, 'request_id': request.state.request_id}
