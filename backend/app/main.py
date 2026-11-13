import uuid
import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from app.api.v1.router import router
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.session import build_database
from app.services.operations import OperationRunner


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine, factory = build_database(settings.database_url.get_secret_value())

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        runner = OperationRunner(engine, factory, settings.mock_chunk_delay, settings=settings)
        runner.start()
        app.state.runner = runner
        try:
            yield
        finally:
            runner.stop()
            engine.dispose()

    app = FastAPI(title='TalentGo API', version='0.3.0', lifespan=lifespan,
                  description='M3: explicit model modes, four skills and evidence-validated training scores.')
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = factory

    @app.middleware('http')
    async def request_id(request: Request, call_next):
        request.state.request_id = str(uuid.uuid4())
        result = await call_next(request)
        result.headers['X-Request-ID'] = request.state.request_id
        result.headers['Cache-Control'] = 'no-store'
        result.headers['X-Content-Type-Options'] = 'nosniff'
        return result

    def error_response(request: Request, status: int, code: str, message: str, details=None):
        headers = {'WWW-Authenticate': 'Bearer'} if status == 401 else None
        return JSONResponse(status_code=status, headers=headers, content={
            'error': {'code': code, 'message': message, 'details': details or {}},
            'request_id': getattr(request.state, 'request_id', None),
        })

    @app.exception_handler(AppError)
    async def domain_error(request: Request, error: AppError):
        return error_response(request, error.status, error.code, error.message, error.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        fields = [{'field': '.'.join(str(x) for x in e['loc']), 'type': e['type']} for e in error.errors()]
        return error_response(request, 422, 'VALIDATION_ERROR', '请检查输入内容', {'fields': fields})

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError):
        frames = traceback.extract_tb(error.__traceback__)
        logging.getLogger(__name__).error('Database failure sqlstate=%s location=%s',
            getattr(getattr(error, 'orig', None), 'sqlstate', None),
            [(frame.name, frame.lineno) for frame in frames if '/app/' in frame.filename.replace('\\', '/')])
        return error_response(request, 503, 'DATABASE_UNAVAILABLE', '数据库暂时不可用，请稍后重试')

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        return error_response(request, error.status_code, 'RESOURCE_NOT_FOUND' if error.status_code == 404 else 'HTTP_ERROR',
                              '资源不存在' if error.status_code == 404 else '请求未能完成')

    app.include_router(router)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_methods=['GET', 'POST', 'PATCH', 'DELETE', 'OPTIONS'],
                       allow_headers=['Authorization', 'Content-Type', 'Idempotency-Key', 'Last-Event-ID'],
                       expose_headers=['X-Request-ID'])
    return app


app = create_app()
