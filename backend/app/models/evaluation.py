import uuid
from decimal import Decimal
from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, IdentityMixin


class Evaluation(IdentityMixin, Base):
    __tablename__ = 'evaluations'
    __table_args__ = (
        ForeignKeyConstraint(['question_id', 'session_id'], ['questions.id', 'questions.session_id'],
                             name='fk_evaluation_question_session', ondelete='CASCADE'),
        UniqueConstraint('question_id', 'revision'),
        CheckConstraint("scope IN ('provisional','final')", name='scope'),
        CheckConstraint('question_score IS NULL OR question_score BETWEEN 0 AND 100', name='score'),
        Index('uq_evaluation_final', 'question_id', unique=True, postgresql_where=text("scope='final'")),
    )
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('interview_sessions.id', ondelete='CASCADE'))
    question_id: Mapped[uuid.UUID]
    operation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('operations.id', ondelete='CASCADE'))
    revision: Mapped[int] = mapped_column(Integer)
    scope: Mapped[str] = mapped_column(String(16))
    dimensions: Mapped[dict] = mapped_column(JSONB)
    missing_points: Mapped[list] = mapped_column(JSONB)
    suggestion: Mapped[str] = mapped_column(Text)
    flag: Mapped[str] = mapped_column(String(32))
    question_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    context_hash: Mapped[str] = mapped_column(String(128))
    rubric_version: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(24))
    model_name: Mapped[str] = mapped_column(String(120))
