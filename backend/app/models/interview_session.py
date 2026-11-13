import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdentityMixin


class InterviewSession(IdentityMixin, Base):
    __tablename__ = 'interview_sessions'
    __table_args__ = (
        CheckConstraint("status IN ('clarifying','ready','interviewing','paused','evaluating','completed','aborted')", name='status'),
        CheckConstraint("role IS NULL OR role IN ('frontend','backend')", name='role'),
        CheckConstraint("mode IS NULL OR mode IN ('technical','behavioral','pressure')", name='mode'),
        CheckConstraint('version > 0', name='version'),
        ForeignKeyConstraint(['current_question_id', 'id'], ['questions.id', 'questions.session_id'],
                             name='fk_session_current_question', use_alter=True, deferrable=True, initially='DEFERRED'),
        Index('ix_interview_sessions_user_created', 'user_id', 'created_at', 'id'),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    title: Mapped[str] = mapped_column(String(120), default='我的模拟面试')
    role: Mapped[str | None] = mapped_column(String(32))
    mode: Mapped[str | None] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24))
    config: Mapped[dict] = mapped_column(JSONB)
    profile_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    provider: Mapped[str] = mapped_column(String(24), default='mock')
    model_name: Mapped[str | None] = mapped_column(String(120))
    source_task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('practice_tasks.id', ondelete='SET NULL', use_alter=True, name='fk_session_source_task'))
    model_base_url: Mapped[str | None] = mapped_column(String(500))
    rubric_version: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1)
    current_question_id: Mapped[uuid.UUID | None]
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
