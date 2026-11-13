from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / '.env', env_file_encoding='utf-8', extra='ignore'
    )
    app_env: Literal['development', 'test'] = 'development'
    database_url: SecretStr
    test_database_url: SecretStr | None = None
    cors_origins: list[str] = ['http://localhost:5173', 'http://127.0.0.1:5173']
    llm_provider: Literal['mock', 'deepseek'] = 'mock'
    mock_chunk_delay: float = Field(default=0.04, ge=0, le=0.5)

    @field_validator('database_url', 'test_database_url')
    @classmethod
    def validate_database(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None:
            try:
                url = make_url(value.get_secret_value())
                valid = url.drivername == 'postgresql+psycopg' and url.port == 6543 and url.database
            except Exception:
                valid = False
            if not valid:
                raise ValueError('Use a PostgreSQL psycopg URL with port 6543 and a database name')
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
