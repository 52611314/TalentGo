from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Query, Request
from app.api.deps import CurrentUser, DB, response
from app.services import practice, memory

router = APIRouter(tags=['practice'])


@router.get('/practice-tasks')
def tasks(db: DB, user: CurrentUser, request: Request, limit: int = Query(20, ge=1, le=100),
          offset: int = Query(0, ge=0, le=10000), status: Literal['pending','in_progress','completed'] | None = None):
    return response(request, practice.tasks(db, user.id, limit, offset, status))


@router.get('/practice-tasks/{tid}')
def task(tid: UUID, db: DB, user: CurrentUser, request: Request):
    return response(request, practice.task_data(practice.owned_task(db, user.id, tid)))


@router.get('/reports/trends')
def trends(db: DB, user: CurrentUser, request: Request, limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0, le=10000)):
    return response(request, practice.trends(db, user.id, limit, offset))


@router.get('/sessions/{sid}/memory-usages')
def usage(sid: UUID, db: DB, user: CurrentUser, request: Request):
    return response(request, memory.usage_data(db, user.id, sid))
