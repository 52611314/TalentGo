import uuid
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, IdentityMixin


class Memory(IdentityMixin, Base):
    __tablename__ = 'memories'
    __table_args__ = (CheckConstraint("kind IN ('goal','preference','weakness')", name='kind'),
                     CheckConstraint("source_type IN ('user_explicit','system_inferred')", name='source'),
                     CheckConstraint('version > 0', name='version'))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    topic: Mapped[str] = mapped_column(String(80))
    role: Mapped[str | None] = mapped_column(String(32))
    mode: Mapped[str | None] = mapped_column(String(24))
    content: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(32))
    source_session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('interview_sessions.id', ondelete='CASCADE'))
    source_evaluation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('evaluations.id', ondelete='CASCADE'))
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
