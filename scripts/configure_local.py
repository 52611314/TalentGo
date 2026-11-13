"""Create missing ignored local configuration; never display credentials."""
from pathlib import Path
import secrets
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]


def main():
    root_env = ROOT / '.env'
    if not root_env.exists():
        root_env.write_text('POSTGRES_DB=talentgo\nPOSTGRES_USER=talentgo_app\n'
                            f'POSTGRES_PASSWORD={secrets.token_hex(24)}\nPOSTGRES_PORT=6543\n', encoding='utf-8')
    values = {}
    for line in root_env.read_text(encoding='utf-8-sig').splitlines():
        key, separator, value = line.partition('=')
        if separator and not key.lstrip().startswith('#'):
            values[key.strip()] = value.strip().strip('\"\'')
    required = ('POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD')
    if any(not values.get(key) for key in required) or values.get('POSTGRES_PORT', '6543') != '6543':
        raise SystemExit('Root .env must define database, user, password and port 6543; existing file was not changed.')
    if values['POSTGRES_PASSWORD'].startswith('replace-with-'):
        raise SystemExit('Replace the sample database password in ignored .env before setup.')
    db = values['POSTGRES_DB']
    user, password = quote(values['POSTGRES_USER'], safe=''), quote(values['POSTGRES_PASSWORD'], safe='')
    backend_env = ROOT / 'backend/.env'
    if not backend_env.exists():
        prefix = f'postgresql+psycopg://{user}:{password}@localhost:6543/'
        backend_env.write_text('APP_ENV=development\n' + f'DATABASE_URL={prefix}{db}\n'
                               f'TEST_DATABASE_URL={prefix}{db}_test\n'
                               'CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]\n'
                               'LLM_PROVIDER=mock\n', encoding='utf-8')
    frontend_env = ROOT / 'frontend/.env'
    if not frontend_env.exists():
        frontend_env.write_text('VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1\n', encoding='utf-8')
    print('Local environment files ready. Existing files preserved; no credentials displayed.')


if __name__ == '__main__':
    main()
