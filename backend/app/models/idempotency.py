import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdentityMixin


class IdempotencyReceipt(IdentityMixin, Base):
    """M1 synchronous mutation receipts; long-running operations belong to M2."""
    __tablename__ = 'idempotency_receipts'
    __table_args__ = (UniqueConstraint('user_id', 'key_hash'),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    key_hash: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(128))
    response_data: Mapped[dict] = mapped_column(JSONB)
