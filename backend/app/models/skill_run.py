import uuid
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, IdentityMixin


class SkillRun(IdentityMixin, Base):
    __tablename__ = 'skill_runs'
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('interview_sessions.id', ondelete='CASCADE'), index=True)
    operation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('operations.id', ondelete='CASCADE'))
    attempt_no: Mapped[int] = mapped_column(Integer)
    skill_key: Mapped[str] = mapped_column(String(40))
    skill_version: Mapped[str] = mapped_column(String(64))
    phase: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(24))
    model_name: Mapped[str] = mapped_column(String(120))
    input_refs: Mapped[dict] = mapped_column(JSONB)
    usage: Mapped[dict] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(80))
