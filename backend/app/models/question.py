import uuid
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, IdentityMixin


class Question(IdentityMixin, Base):
    __tablename__ = 'questions'
    __table_args__ = (
        UniqueConstraint('id', 'session_id'), UniqueConstraint('session_id', 'ordinal'),
        CheckConstraint("status IN ('open','answered','skipped','unscored')", name='status'),
        CheckConstraint('ordinal > 0 AND difficulty BETWEEN 1 AND 3 AND followup_count BETWEEN 0 AND 2', name='bounds'),
    )
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('interview_sessions.id', ondelete='CASCADE'))
    ordinal: Mapped[int] = mapped_column(Integer)
    topic: Mapped[str] = mapped_column(String(80))
    content: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default='open')
    followup_count: Mapped[int] = mapped_column(Integer, default=0)
    hint_used: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    source_key: Mapped[str | None] = mapped_column(String(120))
    rubric_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
