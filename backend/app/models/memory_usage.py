import uuid
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, IdentityMixin


class MemoryUsage(IdentityMixin, Base):
    __tablename__ = 'memory_usages'
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('interview_sessions.id', ondelete='CASCADE'), index=True)
    operation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('operations.id', ondelete='CASCADE'))
    attempt_no: Mapped[int] = mapped_column(Integer)
    memory_id: Mapped[uuid.UUID]  # Opaque reference survives deletion; never stores copied content.
    memory_version: Mapped[int] = mapped_column(Integer)
    memory_revision: Mapped[int] = mapped_column(Integer)
    phase: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(String(160))
