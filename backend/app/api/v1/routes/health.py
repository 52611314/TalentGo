from fastapi import APIRouter, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import DB, response
from app.core.errors import AppError

router = APIRouter(prefix='/health', tags=['health'])
MIGRATION_HEAD = '0003_m3_skills'


@router.get('/live')
def live(request: Request):
    return response(request, {'status': 'ok', 'app': 'TalentGo', 'milestone': 'M3', 'version': '0.3.0'})


@router.get('/ready')
def ready(db: DB, request: Request):
    try:
        db.execute(text('SELECT 1'))
        versions = db.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
    except SQLAlchemyError:
        raise AppError(503, 'DATABASE_UNAVAILABLE', '数据库尚未就绪，请检查连接与迁移') from None
    if versions != [MIGRATION_HEAD]:
        raise AppError(503, 'SCHEMA_NOT_READY', '数据库迁移版本与应用不一致')
    return response(request, {'status': 'ready', 'database': 'PostgreSQL', 'port': 6543,
                             'schema_revision': MIGRATION_HEAD, 'milestone': 'M3'})
