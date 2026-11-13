import uuid
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, IdentityMixin


class Operation(IdentityMixin, Base):
    __tablename__ = 'operations'
    __table_args__ = (
        UniqueConstraint('user_id', 'key_hash'),
        CheckConstraint("status IN ('queued','running','succeeded','failed','cancelled')", name='status'),
        CheckConstraint('attempt_no > 0 AND expected_session_version > 0', name='bounds'),
        Index('uq_operations_active_session', 'session_id', unique=True,
              postgresql_where=text("status IN ('queued','running')")),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('interview_sessions.id', ondelete='CASCADE'))
    kind: Mapped[str] = mapped_column(String(32))
    key_hash: Mapped[str] = mapped_column(String(128))
    request_payload: Mapped[dict] = mapped_column(JSONB)
    expected_session_version: Mapped[int] = mapped_column(Integer)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default='queued')
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    result_refs: Mapped[dict] = mapped_column(JSONB, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(80))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OperationEvent(IdentityMixin, Base):
    __tablename__ = 'operation_events'
    __table_args__ = (UniqueConstraint('operation_id', 'seq'), CheckConstraint('seq > 0', name='seq'))
    operation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('operations.id', ondelete='CASCADE'))
    seq: Mapped[int] = mapped_column(Integer)
    attempt_no: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSONB)
