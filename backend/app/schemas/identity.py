from typing import Annotated

from pydantic import StringConstraints

from app.schemas.common import StrictModel


class IdentityCreate(StrictModel):
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
