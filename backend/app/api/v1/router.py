from fastapi import APIRouter

from app.api.v1.routes import health, identity, profile, sessions, operations

router = APIRouter(prefix='/api/v1')
router.include_router(health.router)
router.include_router(identity.router)
router.include_router(profile.router)
router.include_router(sessions.router)
router.include_router(operations.router)
