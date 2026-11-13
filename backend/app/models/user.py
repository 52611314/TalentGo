from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdentityMixin


class User(IdentityMixin, Base):
    __tablename__ = 'users'
    __table_args__ = (CheckConstraint("status IN ('active', 'revoked')", name='status'),)

    display_name: Mapped[str] = mapped_column(String(60))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    creation_key_hash: Mapped[str] = mapped_column(String(128), unique=True)
    status: Mapped[str] = mapped_column(String(16), default='active')
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
