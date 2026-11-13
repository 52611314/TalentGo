from uuid import UUID
from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse
from app.api.deps import CurrentUser, DB, Key, response
from app.services.interview import operation_data, owned_operation
from app.services.operations import control_operation, event_stream, validate_event_cursor

router = APIRouter(prefix='/operations', tags=['operations'])


@router.get('/{operation_id}')
def get(operation_id: UUID, db: DB, user: CurrentUser, request: Request):
    return response(request, operation_data(db, owned_operation(db, user.id, operation_id)))


@router.post('/{operation_id}/cancel')
def cancel(operation_id: UUID, db: DB, user: CurrentUser, key: Key, request: Request):
    return response(request, control_operation(db, user.id, operation_id, key))


@router.post('/{operation_id}/retry', status_code=202)
def retry(operation_id: UUID, db: DB, user: CurrentUser, key: Key, request: Request):
    result = control_operation(db, user.id, operation_id, key, True)
    operation = owned_operation(db, user.id, operation_id)
    if operation.status == 'queued':
        request.app.state.runner.submit(operation.id, operation.attempt_no)
    return response(request, result)


@router.get('/{operation_id}/events')
def events(operation_id: UUID, db: DB, user: CurrentUser, request: Request,
           last_event_id: str | None = Header(None, max_length=100)):
    after = validate_event_cursor(db, user.id, operation_id, last_event_id)
    db.rollback()  # Do not hold the authentication query's connection for the life of the stream.
    return StreamingResponse(event_stream(request.app.state.session_factory, operation_id, after),
                             media_type='text/event-stream', headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'no-store'})
