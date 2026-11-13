import uuid
from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, IdentityMixin


class PracticeTask(IdentityMixin, Base):
    __tablename__ = 'practice_tasks'
    __table_args__ = (CheckConstraint("status IN ('pending','in_progress','completed')", name='status'),)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    source_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('interview_sessions.id', ondelete='CASCADE'))
    source_evaluation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('evaluations.id', ondelete='CASCADE'), unique=True)
    role: Mapped[str] = mapped_column(String(32))
    mode: Mapped[str] = mapped_column(String(24))
    topic: Mapped[str] = mapped_column(String(80))
    instruction: Mapped[str] = mapped_column(Text)
    seed: Mapped[dict] = mapped_column(JSONB)
    rubric_version: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default='pending')
