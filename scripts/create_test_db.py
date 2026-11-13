"""Create the dedicated test database when absent; do not reset existing data."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from sqlalchemy import create_engine, make_url, text
from app.core.config import get_settings

settings = get_settings()
if settings.test_database_url is None:
    raise SystemExit('TEST_DATABASE_URL is required.')
target = make_url(settings.test_database_url.get_secret_value())
development = make_url(settings.database_url.get_secret_value())
if (not target.database or not target.database.endswith('_test') or target.database == development.database
        or target.host != development.host or target.port != 6543
        or not re.fullmatch(r'[a-z][a-z0-9_]*', target.database)):
    raise SystemExit('Refusing an unsafe or non-test database name/host/port.')
engine = create_engine(settings.database_url.get_secret_value(), isolation_level='AUTOCOMMIT')
with engine.connect() as db:
    exists = db.execute(text('SELECT 1 FROM pg_database WHERE datname=:name'), {'name': target.database}).scalar()
    if not exists:
        db.exec_driver_sql('CREATE DATABASE "' + target.database + '"')
print('Dedicated test database ready; existing data was not reset.')
engine.dispose()
