from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from app.core.errors import AppError
from app.core.security import generate_token, hash_password, hash_secret, verify_password
from app.models import AuthSession, Profile, User
from app.schemas.profile import ProfileRead

# Used for unknown accounts too, so both login paths do a password derivation.
_DUMMY_HASH = hash_password(generate_token())


def new_account(db, username, password):
    user = User(username=username, display_name=username, password_hash=hash_password(password),
                token_hash=hash_secret(generate_token()), creation_key_hash=hash_secret(generate_token()))
    db.add(user)
    db.flush()
    db.add(Profile(user_id=user.id))
    db.flush()
    return user


def issue_session(db, user):
    token = generate_token()
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.expires_at <= datetime.now(timezone.utc)))
    db.add(AuthSession(user_id=user.id, token_hash=hash_secret(token), expires_at=expires))
    profile = db.scalar(select(Profile).where(Profile.user_id == user.id))
    data = {'user_id': str(user.id), 'username': user.username, 'display_name': user.display_name,
            'token': token, 'expires_at': expires.isoformat(),
            'profile': ProfileRead.model_validate(profile).model_dump(mode='json')}
    db.commit()
    return data


def register(db, credentials):
    try:
        user = new_account(db, credentials.username, credentials.password)
        return issue_session(db, user)
    except IntegrityError:
        db.rollback()
        raise AppError(409, 'USERNAME_TAKEN', '账号已存在，请换一个账号或直接登录') from None


def login(db, credentials):
    user = db.scalar(select(User).where(User.username == credentials.username))
    valid = verify_password(credentials.password, user.password_hash if user and user.password_hash else _DUMMY_HASH)
    if not valid or not user or user.status != 'active':
        raise AppError(401, 'INVALID_CREDENTIALS', '账号或密码错误')
    return issue_session(db, user)


def seed_local_admin(db):
    """Development-only test account. Never reset an existing account's password."""
    if db.scalar(select(User.id).where(User.username == 'admin')):
        return
    try:
        new_account(db, 'admin', 'password')
        db.commit()
    except IntegrityError:
        db.rollback()
