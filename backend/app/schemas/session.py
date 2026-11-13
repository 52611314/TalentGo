from typing import Literal
from uuid import UUID
from pydantic import Field, model_validator
from app.schemas.common import StrictModel
from app.schemas.profile import Role

Mode = Literal['technical', 'behavioral', 'pressure']


class SessionConfig(StrictModel):
    question_count: int = Field(default=5, ge=1, le=10, strict=True)
    difficulty: int = Field(default=1, ge=1, le=3, strict=True)
    max_followups: int = Field(default=1, ge=0, le=2, strict=True)
    pressure_level: int = Field(default=1, ge=1, le=3, strict=True)
    pressure_consent: bool = Field(default=False, strict=True)


class SessionCreate(StrictModel):
    title: str = Field(default='我的模拟面试', min_length=1, max_length=120)
    role: Role | None = None
    mode: Mode | None = None
    config: SessionConfig = Field(default_factory=SessionConfig)


class SessionPatch(StrictModel):
    expected_version: int = Field(ge=1, strict=True)
    title: str | None = Field(default=None, min_length=1, max_length=120)
    role: Role | None = None
    mode: Mode | None = None
    config: SessionConfig | None = None

    @model_validator(mode='after')
    def fields_valid(self):
        changed = self.model_fields_set - {'expected_version'}
        if not changed or any(getattr(self, k) is None for k in changed & {'title', 'config'}):
            raise ValueError('Provide a nonempty configuration patch')
        return self


class SessionMessage(StrictModel):
    expected_version: int = Field(ge=1, strict=True)
    kind: Literal['clarification', 'answer']
    content: str = Field(min_length=1, max_length=8000)
    question_id: UUID | None = None

    @model_validator(mode='after')
    def content_valid(self):
        self.content = self.content.strip()
        if not self.content or (self.kind == 'answer' and self.question_id is None):
            raise ValueError('A nonempty answer requires question_id')
        return self


class SessionAction(StrictModel):
    expected_version: int = Field(ge=1, strict=True)
    action: Literal['clarify', 'start', 'hint', 'skip', 'pause', 'resume', 'lower_pressure', 'finish', 'abort']
    pressure_level: int | None = Field(default=None, ge=1, le=3, strict=True)
