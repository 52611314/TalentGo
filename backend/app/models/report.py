import uuid
from decimal import Decimal
from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, IdentityMixin


class Report(IdentityMixin, Base):
    __tablename__ = 'reports'
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('interview_sessions.id', ondelete='CASCADE'), unique=True)
    status: Mapped[str] = mapped_column(String(16), default='ready')
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True)
    coverage: Mapped[dict] = mapped_column(JSONB)
    summary: Mapped[str] = mapped_column(Text)
    total_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
