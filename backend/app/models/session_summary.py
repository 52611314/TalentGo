import uuid
from sqlalchemy import ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, IdentityMixin


class SessionSummary(IdentityMixin, Base):
    __tablename__ = 'session_summaries'
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('interview_sessions.id', ondelete='CASCADE'), unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    memory_revision: Mapped[int] = mapped_column(Integer)
    profile_version: Mapped[int] = mapped_column(Integer)
    covered_through_ordinal: Mapped[int] = mapped_column(Integer)
    content: Mapped[dict] = mapped_column(JSONB)
