from fastapi import APIRouter, Request

from app.api.deps import CurrentUser, DB, Key, response
from app.schemas.profile import ProfilePatch
from app.services.profile import read_profile, update_profile

router = APIRouter(prefix='/profile', tags=['profile'])


@router.get('')
def get(user: CurrentUser, db: DB, request: Request):
    return response(request, read_profile(db, user))


@router.patch('')
def patch(body: ProfilePatch, user: CurrentUser, db: DB, key: Key, request: Request):
    return response(request, update_profile(db, user, body, key))
