from typing import Annotated
from pydantic import Field, StringConstraints, field_validator
from app.schemas.common import StrictModel


class Credentials(StrictModel):
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=32, pattern=r'^[A-Za-z0-9_]+$')]
    password: str = Field(min_length=8, max_length=128, repr=False)

    @field_validator('username')
    @classmethod
    def normalize(cls, value):
        return value.lower()
