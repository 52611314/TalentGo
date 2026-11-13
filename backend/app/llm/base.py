from dataclasses import dataclass
from typing import Any, Callable, Protocol
from pydantic import BaseModel


@dataclass
class ModelResult:
    value: BaseModel
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int
    attempts: int


class JsonProvider(Protocol):
    def generate(self, schema: type[BaseModel], system: str, context: dict,
                 check: Callable[[], None], validate: Callable[[Any], None] | None = None) -> ModelResult: ...
