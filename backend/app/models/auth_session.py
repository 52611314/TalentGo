import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, IdentityMixin


class AuthSession(IdentityMixin, Base):
    __tablename__ = 'auth_sessions'
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
