from fastapi import APIRouter

from app.api.v1.routes import health, identity, profile, sessions, operations, models, memories, practice

router = APIRouter(prefix='/api/v1')
router.include_router(health.router)
router.include_router(identity.router)
router.include_router(profile.router)
router.include_router(sessions.router)
router.include_router(operations.router)
router.include_router(models.router)
router.include_router(memories.router)
router.include_router(practice.router)
