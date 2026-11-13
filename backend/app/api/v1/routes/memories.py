from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Query, Request
from app.api.deps import CurrentUser, DB, Key, response
from app.schemas.memory import MemoryCreate, MemoryPatch
from app.services import memory

router = APIRouter(prefix='/memories', tags=['memory'])


@router.get('')
def listing(db: DB, user: CurrentUser, request: Request, limit: int = Query(50, ge=1, le=100),
            offset: int = Query(0, ge=0, le=10000), kind: Literal['goal','preference','weakness'] | None = None):
    return response(request, memory.listing(db, user.id, limit, offset, kind))


@router.post('', status_code=201)
def create(body: MemoryCreate, db: DB, user: CurrentUser, key: Key, request: Request):
    return response(request, memory.mutate(db, user.id, key, body))


@router.patch('/{mid}')
def patch(mid: UUID, body: MemoryPatch, db: DB, user: CurrentUser, key: Key, request: Request):
    return response(request, memory.mutate(db, user.id, key, body, mid))


@router.delete('/{mid}')
def remove(mid: UUID, db: DB, user: CurrentUser, key: Key, request: Request, expected_version: int = Query(ge=1)):
    return response(request, memory.mutate(db, user.id, key, {'expected_version': expected_version}, mid, True))
