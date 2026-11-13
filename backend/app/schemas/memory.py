from typing import Literal
from pydantic import Field, model_validator
from app.schemas.common import StrictModel


class MemoryCreate(StrictModel):
    kind: Literal['goal', 'preference', 'weakness']
    topic: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=1, max_length=1200)
    role: Literal['frontend', 'backend'] | None = None
    mode: Literal['technical', 'behavioral', 'pressure'] | None = None

    @model_validator(mode='after')
    def trim(self):
        self.topic, self.content = self.topic.strip(), self.content.strip()
        if not self.topic or not self.content:
            raise ValueError('Nonempty memory required')
        return self


class MemoryPatch(StrictModel):
    expected_version: int = Field(ge=1, strict=True)
    content: str | None = Field(default=None, min_length=1, max_length=1200)
    topic: str | None = Field(default=None, min_length=1, max_length=80)
    confirmed: bool | None = Field(default=None, strict=True)

    @model_validator(mode='after')
    def trim(self):
        changed = self.model_fields_set - {'expected_version'}
        if not changed or any(getattr(self, k) is None for k in changed):
            raise ValueError('Nonempty patch required')
        for key in changed & {'content', 'topic'}:
            setattr(self, key, getattr(self, key).strip())
            if not getattr(self, key): raise ValueError('Nonempty value required')
        return self
