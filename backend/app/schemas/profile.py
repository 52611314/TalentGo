import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from app.schemas.common import StrictModel

TechItem = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Role = Literal['frontend', 'backend']
Level = Literal['beginner', 'intern', 'graduate']
Style = Literal['concise', 'detailed', 'guided']


class ProfileRead(StrictModel):
    id: uuid.UUID
    user_id: uuid.UUID
    target_role: Role | None
    experience_level: Level | None
    tech_stack: list[str]
    background: str
    goals: str
    feedback_style: Style
    allow_inferred_memory: bool
    version: int
    memory_revision: int
    updated_at: datetime


class ProfilePatch(StrictModel):
    expected_version: int = Field(ge=1, strict=True)
    target_role: Role | None = None
    experience_level: Level | None = None
    tech_stack: list[TechItem] | None = Field(default=None, max_length=20)
    background: str | None = Field(default=None, max_length=4000)
    goals: str | None = Field(default=None, max_length=4000)
    feedback_style: Style | None = None
    allow_inferred_memory: bool | None = Field(default=None, strict=True)

    @model_validator(mode='after')
    def validate_patch(self):
        changed = self.model_fields_set - {'expected_version'}
        if not changed:
            raise ValueError('Provide at least one profile field')
        nullable = {'target_role', 'experience_level'}
        if any(getattr(self, key) is None for key in changed - nullable):
            raise ValueError('Only target_role and experience_level can be null')
        return self
