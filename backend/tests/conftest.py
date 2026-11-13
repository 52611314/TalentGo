import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import make_url, text

from app.core.config import Settings
from app.main import create_app

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='session')
def test_app():
    local = Settings()
    raw = os.getenv('TEST_DATABASE_URL') or (local.test_database_url.get_secret_value() if local.test_database_url else '')
    if not raw:
        pytest.fail('Configure TEST_DATABASE_URL for the dedicated PostgreSQL test database')
    url = make_url(raw)
    development = make_url(local.database_url.get_secret_value())
    if not url.database or not url.database.endswith('_test') or url.database == development.database or url.port != 6543:
        pytest.fail('Refusing to run against a non-test database or a port other than 6543')
    settings = Settings(database_url=SecretStr(raw), app_env='test', mock_chunk_delay=0.001)
    app = create_app(settings)
    previous = os.environ.get('DATABASE_URL')
    os.environ['DATABASE_URL'] = raw
    from app.core.config import get_settings
    get_settings.cache_clear()
    try:
        config = Config(str(ROOT / 'backend/alembic.ini'))
        command.upgrade(config, 'head')
        yield app
    finally:
        app.state.engine.dispose()
        if previous is None:
            os.environ.pop('DATABASE_URL', None)
        else:
            os.environ['DATABASE_URL'] = previous
        get_settings.cache_clear()


@pytest.fixture
def client(test_app):
    with test_app.state.engine.begin() as connection:
        connection.execute(text('TRUNCATE idempotency_receipts, profiles, users CASCADE'))
    with TestClient(test_app) as client:
        yield client
