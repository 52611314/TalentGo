from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Query, Request, Response
from app.api.deps import CurrentUser, DB, Key, response
from app.schemas.session import SessionAction, SessionCreate, SessionMessage, SessionPatch
from app.services import interview
from app.services.operations import owned_operation

router = APIRouter(prefix='/sessions', tags=['sessions'])


@router.get('/{session_id}/report/export')
def export(session_id: UUID, db: DB, user: CurrentUser, format: Literal['markdown','json'] = 'markdown'):
    from app.services.exporting import export_report
    text, media = export_report(db,user.id,session_id,format)
    extension='json' if format=='json' else 'md'
    return Response(content=text,media_type=media,headers={'Content-Disposition':f'attachment; filename="talentgo-{session_id}.{extension}"'})


def dispatch(request, db, user_id, result):
    if result.get('operation_id'):
        operation = owned_operation(db, user_id, UUID(result['operation_id']))
        if operation.status == 'queued':
            request.app.state.runner.submit(operation.id, operation.attempt_no)


@router.post('', status_code=201)
def create(body: SessionCreate, db: DB, user: CurrentUser, key: Key, request: Request):
    return response(request, interview.create_session(db, user.id, body, key, request.app.state.settings))


@router.get('')
def list_(db: DB, user: CurrentUser, request: Request, limit: int = Query(20, ge=1, le=100),
          cursor: str | None = Query(None, max_length=512), status: str | None = None):
    return response(request, interview.list_sessions(db, user.id, limit, cursor, status))


@router.get('/{session_id}')
def get(session_id: UUID, db: DB, user: CurrentUser, request: Request):
    return response(request, interview.session_data(db, interview.owned_session(db, user.id, session_id)))


@router.patch('/{session_id}')
def patch(session_id: UUID, body: SessionPatch, db: DB, user: CurrentUser, key: Key, request: Request):
    return response(request, interview.patch_session(db, user.id, session_id, body, key))


@router.get('/{session_id}/messages')
def messages(session_id: UUID, db: DB, user: CurrentUser, request: Request, limit: int = Query(100, ge=1, le=100),
             cursor: str | None = Query(None, max_length=512)):
    return response(request, interview.list_messages(db, user.id, session_id, limit, cursor))


@router.post('/{session_id}/messages', status_code=202)
def message(session_id: UUID, body: SessionMessage, db: DB, user: CurrentUser, key: Key, request: Request):
    result = interview.submit(db, user.id, session_id, body, key, True)
    dispatch(request, db, user.id, result)
    return response(request, result)


@router.post('/{session_id}/actions')
def action(session_id: UUID, body: SessionAction, db: DB, user: CurrentUser, key: Key, request: Request, http_response: Response):
    result = interview.submit(db, user.id, session_id, body, key)
    dispatch(request, db, user.id, result)
    http_response.status_code = 202 if result.get('operation_id') else 200
    return response(request, result)


@router.get('/{session_id}/report')
def report(session_id: UUID, db: DB, user: CurrentUser, request: Request):
    return response(request, interview.report_data(db, user.id, session_id))


@router.get('/{session_id}/trace')
def trace(session_id: UUID, db: DB, user: CurrentUser, request: Request):
    return response(request, interview.trace_data(db, user.id, session_id))


@router.delete('/{session_id}', status_code=204)
def delete(session_id: UUID, db: DB, user: CurrentUser, key: Key, expected_version: int = Query(ge=1)):
    interview.delete_session(db, user.id, session_id, expected_version, key)
