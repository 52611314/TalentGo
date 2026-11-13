import json

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import hash_secret
from app.models import IdempotencyReceipt, Profile, User
from app.repositories.users import find_profile
from app.schemas.profile import ProfilePatch, ProfileRead


def read_profile(db: Session, user: User) -> dict:
    profile = find_profile(db, user.id)
    if profile is None:
        raise AppError(404, 'RESOURCE_NOT_FOUND', '资料不存在')
    return ProfileRead.model_validate(profile).model_dump(mode='json')


def update_profile(db: Session, user: User, patch: ProfilePatch, key: str) -> dict:
    payload = patch.model_dump(exclude_unset=True, mode='json')
    digest = hash_secret('PATCH /api/v1/profile\n' + json.dumps(payload, sort_keys=True, ensure_ascii=False))
    key_hash = hash_secret(key)
    # Serializes per-user receipts, including identical concurrent retries.
    db.execute(select(User.id).where(User.id == user.id).with_for_update(key_share=True))
    receipt = db.scalar(select(IdempotencyReceipt).where(
        IdempotencyReceipt.user_id == user.id, IdempotencyReceipt.key_hash == key_hash))
    if receipt:
        if receipt.request_hash != digest:
            raise AppError(409, 'IDEMPOTENCY_CONFLICT', '该请求键已用于不同内容')
        return receipt.response_data
    values = {k: v for k, v in payload.items() if k != 'expected_version'}
    changed = db.execute(update(Profile).where(Profile.user_id == user.id, Profile.version == patch.expected_version)
        .values(**values, version=Profile.version + 1).returning(Profile.id)).scalar_one_or_none()
    if changed is None:
        current = find_profile(db, user.id)
        raise AppError(409, 'VERSION_CONFLICT', '资料已变更，请刷新后再保存',
                       {'current_version': current.version if current else None})
    db.expire_all()
    result = read_profile(db, user)
    db.add(IdempotencyReceipt(user_id=user.id, key_hash=key_hash, request_hash=digest, response_data=result))
    db.commit()
    return result
