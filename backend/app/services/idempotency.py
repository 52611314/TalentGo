import json
from sqlalchemy import select
from app.models import IdempotencyReceipt, User
from app.core.security import hash_secret
from app.core.errors import AppError


def begin_request(db, user_id, key, method, path, payload):
    # Serialize this user's mutations without blocking FK KEY SHARE checks in workers.
    db.execute(select(User.id).where(User.id == user_id).with_for_update(key_share=True))
    digest = hash_secret(method + ' ' + path + '\n' + json.dumps(payload, sort_keys=True, ensure_ascii=False))
    key_hash = hash_secret(key)
    receipt = db.scalar(select(IdempotencyReceipt).where(
        IdempotencyReceipt.user_id == user_id, IdempotencyReceipt.key_hash == key_hash))
    if receipt and receipt.request_hash != digest:
        raise AppError(409, 'IDEMPOTENCY_CONFLICT', '该请求键已用于不同请求')
    return receipt, key_hash, digest


def save_receipt(db, user_id, key_hash, digest, result):
    db.add(IdempotencyReceipt(user_id=user_id, key_hash=key_hash, request_hash=digest, response_data=result))
