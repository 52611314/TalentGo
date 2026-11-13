from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator
from app.schemas.common import StrictModel

DIMENSIONS = ('relevance', 'accuracy_consistency', 'reasoning', 'evidence_detail', 'communication')
Score = Annotated[Decimal, Field(ge=0, le=5, max_digits=3, decimal_places=2)]


class Evidence(StrictModel):
    message_id: UUID
    quote: str = Field(min_length=1, max_length=800)


class Dimension(StrictModel):
    score: Score | None
    reason: str = Field(min_length=1, max_length=1200)
    evidence: list[Evidence] = Field(max_length=5)

    @model_validator(mode='after')
    def scored_requires_evidence(self):
        if self.score is not None and not self.evidence:
            raise ValueError('A numerical score requires quoted user evidence')
        return self


class Dimensions(StrictModel):
    relevance: Dimension
    accuracy_consistency: Dimension
    reasoning: Dimension
    evidence_detail: Dimension
    communication: Dimension


class AnswerEvaluation(StrictModel):
    dimensions: Dimensions
    flag: Literal['normal', 'vague', 'off_topic', 'idk', 'critical_error']
    missing_points: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(max_length=8)
    suggestion: str = Field(min_length=1, max_length=1500)
    followup: str | None = Field(max_length=1200)


class GeneratedQuestion(StrictModel):
    topic: str = Field(min_length=1, max_length=80)
    question: str = Field(min_length=5, max_length=1800)


class GeneratedHint(StrictModel):
    hint: str = Field(min_length=5, max_length=1200)


class ClarifiedGoal(StrictModel):
    role: Literal['frontend', 'backend'] | None
    mode: Literal['technical', 'behavioral', 'pressure'] | None
    reply: str = Field(min_length=5, max_length=1200)


class ReviewItem(StrictModel):
    text: str = Field(min_length=1, max_length=800)
    question_ids: list[UUID] = Field(min_length=1, max_length=10)


class InterviewReview(StrictModel):
    summary: str = Field(min_length=1, max_length=2000)
    strengths: list[ReviewItem] = Field(max_length=5)
    gaps: list[ReviewItem] = Field(max_length=5)
    recommendations: list[ReviewItem] = Field(max_length=5)
