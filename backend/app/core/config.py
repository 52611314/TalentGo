from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
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
    llm_api_key: SecretStr | None = Field(default=None, validation_alias=AliasChoices('LLM_API_KEY', 'DEEPSEEK_API_KEY', 'llm_api_key'))
    llm_base_url: str = 'https://api.deepseek.com'
    llm_model: str = 'deepseek-flash'
    llm_timeout_seconds: float = Field(default=60, ge=5, le=120)
    llm_max_tokens: int = Field(default=2400, ge=512, le=4096)
    context_max_characters: int = Field(default=48000, ge=8000, le=100000)

    @field_validator('llm_base_url')
    @classmethod
    def validate_llm_url(cls, value):
        from urllib.parse import urlsplit
        url = urlsplit(value)
        if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError('LLM_BASE_URL must be an HTTPS endpoint without credentials, query or fragment')
        return value.rstrip('/')

    @field_validator('llm_model')
    @classmethod
    def validate_model_name(cls, value):
        if not value.strip() or len(value) > 120:
            raise ValueError('Configure a nonempty model name')
        return value.strip()

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
