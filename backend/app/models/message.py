import uuid
from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, IdentityMixin


class Message(IdentityMixin, Base):
    __tablename__ = 'messages'
    __table_args__ = (
        UniqueConstraint('session_id', 'seq'),
        ForeignKeyConstraint(['question_id', 'session_id'], ['questions.id', 'questions.session_id'],
                             name='fk_messages_question_session', ondelete='CASCADE'),
        CheckConstraint("speaker IN ('user','assistant','system')", name='speaker'),
        CheckConstraint('seq > 0', name='seq'),
    )
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('interview_sessions.id', ondelete='CASCADE'))
    question_id: Mapped[uuid.UUID | None]
    operation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('operations.id', ondelete='SET NULL'))
    seq: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(24))
    content: Mapped[str] = mapped_column(Text)
