from fastapi import APIRouter, Request, Response
from sqlalchemy import delete
from app.api.deps import CurrentUser, DB, response
from app.core.security import hash_secret
from app.models import AuthSession
from app.schemas.auth import Credentials
from app.services import auth

router = APIRouter(prefix='/auth', tags=['auth'])


@router.post('/register', status_code=201)
def register(body: Credentials, db: DB, request: Request):
    return response(request, auth.register(db, body))


@router.post('/login')
def login(body: Credentials, db: DB, request: Request):
    return response(request, auth.login(db, body))


@router.post('/logout', status_code=204)
def logout(user: CurrentUser, db: DB, request: Request):
    token = request.headers['Authorization'].split(' ', 1)[1].strip()
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.token_hash == hash_secret(token)))
    if user.username is None:
        user.status = 'revoked'
    db.commit()
    return Response(status_code=204)
