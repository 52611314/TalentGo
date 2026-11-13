from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Profile, User


def find_active_user(db: Session, token_hash: str) -> User | None:
    return db.scalar(select(User).where(User.token_hash == token_hash, User.status == 'active'))


def find_profile(db: Session, user_id) -> Profile | None:
    return db.scalar(select(Profile).where(Profile.user_id == user_id))
