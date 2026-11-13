import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdentityMixin


class Profile(IdentityMixin, Base):
    __tablename__ = 'profiles'
    __table_args__ = (
        CheckConstraint("target_role IS NULL OR target_role IN ('frontend', 'backend')", name='role'),
        CheckConstraint("experience_level IS NULL OR experience_level IN ('beginner', 'intern', 'graduate')", name='level'),
        CheckConstraint("feedback_style IN ('concise', 'detailed', 'guided')", name='feedback_style'),
        CheckConstraint('version > 0 AND memory_revision > 0', name='versions'),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), unique=True)
    target_role: Mapped[str | None] = mapped_column(String(32))
    experience_level: Mapped[str | None] = mapped_column(String(24))
    tech_stack: Mapped[list[str]] = mapped_column(JSONB, default=list)
    background: Mapped[str] = mapped_column(Text, default='')
    goals: Mapped[str] = mapped_column(Text, default='')
    feedback_style: Mapped[str] = mapped_column(String(24), default='guided')
    allow_inferred_memory: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    memory_revision: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
