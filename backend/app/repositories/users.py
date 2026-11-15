from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuthSession, Profile, User


def find_active_user(db: Session, token_hash: str) -> User | None:
    user = db.scalar(select(User).join(AuthSession, AuthSession.user_id == User.id).where(
        AuthSession.token_hash == token_hash, AuthSession.expires_at > datetime.now(timezone.utc), User.status == 'active'))
    # Preserve access to pre-account records; account users cannot use legacy tokens.
    return user or db.scalar(select(User).where(User.username.is_(None), User.token_hash == token_hash, User.status == 'active'))


def find_profile(db: Session, user_id) -> Profile | None:
    return db.scalar(select(Profile).where(Profile.user_id == user_id))
