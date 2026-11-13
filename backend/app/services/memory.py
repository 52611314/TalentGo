import uuid
from sqlalchemy import delete, func, or_, select
from app.core.errors import AppError
from app.models import Memory, MemoryUsage, Profile, SessionSummary
from app.services.idempotency import begin_request, save_receipt


def serialize(row):
    return {key: str(getattr(row, key)) if isinstance(getattr(row, key), uuid.UUID) else getattr(row, key)
            for key in ['id','kind','topic','content','role','mode','source_type','source_session_id',
                        'source_evaluation_id','confirmed','version']} | {'updated_at': row.updated_at.isoformat()}


def profile_lock(db, user_id):
    return db.scalar(select(Profile).where(Profile.user_id == user_id).with_for_update())


def invalidate(db, profile):
    profile.memory_revision += 1
    db.execute(delete(SessionSummary).where(SessionSummary.user_id == profile.user_id))


def owned(db, user_id, mid):
    row = db.scalar(select(Memory).where(Memory.id == mid, Memory.user_id == user_id))
    if row is None: raise AppError(404, 'RESOURCE_NOT_FOUND', '记忆不存在或不属于当前身份')
    return row


def listing(db, user_id, limit=50, offset=0, kind=None):
    query = select(Memory).where(Memory.user_id == user_id)
    if kind: query = query.where(Memory.kind == kind)
    rows = db.scalars(query.order_by(Memory.updated_at.desc(), Memory.id).offset(offset).limit(limit+1)).all()
    return {'items': [serialize(r) for r in rows[:limit]], 'next_offset': offset+limit if len(rows)>limit else None,
            'memory_revision': db.scalar(select(Profile.memory_revision).where(Profile.user_id == user_id))}


def mutate(db, user_id, key, body=None, mid=None, removing=False):
    method = 'DELETE' if removing else 'PATCH' if mid else 'POST'
    path = '/api/v1/memories' + (f'/{mid}' if mid else '')
    payload = body if isinstance(body, dict) else body.model_dump(mode='json', exclude_unset=True)
    receipt, kh, digest = begin_request(db, user_id, key, method, path, payload)
    if receipt: return receipt.response_data
    profile = profile_lock(db, user_id)
    if mid:
        row = owned(db, user_id, mid)
        if row.version != payload['expected_version']:
            raise AppError(409, 'VERSION_CONFLICT', '记忆已变更，请刷新', {'current_version': row.version})
        if removing: db.delete(row)
        else:
            for field, value in payload.items():
                if field != 'expected_version': setattr(row, field, value)
            # Editing an inferred statement makes it an explicitly accepted statement.
            if 'content' in payload or 'topic' in payload:
                row.source_type, row.confirmed = 'user_explicit', True
                row.source_session_id = row.source_evaluation_id = None
            row.version += 1
    else:
        if db.scalar(select(func.count()).select_from(Memory).where(Memory.user_id == user_id)) >= 200:
            raise AppError(409, 'MEMORY_LIMIT', '最多保存 200 条记忆，请先整理')
        row = Memory(user_id=user_id, **payload, source_type='user_explicit', confirmed=True)
        db.add(row)
    invalidate(db, profile)
    db.flush()
    result = {'id': str(row.id), 'deleted': removing, 'memory_revision': profile.memory_revision}
    # Receipts intentionally contain no copied memory body, so deletion cannot resurrect it via replay.
    save_receipt(db, user_id, kh, digest, result)
    db.commit()
    return result


def rebuild_summary(db, session):
    from app.models import Evaluation, Question
    profile = profile_lock(db, session.user_id)
    rows = db.execute(select(Question, Evaluation).join(Evaluation, Evaluation.question_id == Question.id).where(
        Question.session_id == session.id, Evaluation.scope == 'final').order_by(Question.ordinal)).all()
    # Deterministic summary stores topic coverage and numeric outcomes, never copied memory/assistant prose.
    content = {'completed_topics': [{'ordinal': q.ordinal, 'question_id': str(q.id), 'topic': q.topic,
        'score': float(e.question_score) if e.question_score is not None else None} for q,e in rows]}
    row = db.scalar(select(SessionSummary).where(SessionSummary.session_id == session.id))
    if row is None:
        row = SessionSummary(session_id=session.id, user_id=session.user_id)
        db.add(row)
    row.memory_revision, row.profile_version = profile.memory_revision, profile.version
    row.covered_through_ordinal = max((q.ordinal for q,e in rows), default=0)
    row.content = content


def retrieve(db, session, topic):
    profile = db.scalar(select(Profile).where(Profile.user_id == session.user_id))
    rows = db.scalars(select(Memory).where(Memory.user_id == session.user_id, Memory.confirmed.is_(True),
        or_(Memory.role.is_(None), Memory.role == session.role), or_(Memory.mode.is_(None), Memory.mode == session.mode),
        or_(Memory.source_type == 'user_explicit', profile.allow_inferred_memory)).order_by(Memory.updated_at.desc(), Memory.id)).all()
    # Specific topic weaknesses plus global goals/preferences. No unconfirmed inferred item is injected.
    rows = [r for r in rows if r.kind != 'weakness' or r.topic == topic]
    rows.sort(key=lambda r: (r.topic != topic, r.source_type != 'user_explicit'))
    selected, seen = [], set()
    for row in rows:
        identity = (row.kind, row.topic)
        if identity in seen: continue
        seen.add(identity)
        selected.append(serialize(row) | {'selection_reason': '同主题已确认' if row.topic == topic else '当前岗位全局目标或偏好'})
        if len(selected) == 8: break
    return profile, selected


def usage_data(db, user_id, session_id):
    from app.services.interview import owned_session
    owned_session(db, user_id, session_id)
    rows = db.scalars(select(MemoryUsage).where(MemoryUsage.session_id == session_id).order_by(MemoryUsage.created_at)).all()
    return {'items': [{'id': str(r.id), 'operation_id': str(r.operation_id), 'attempt_no': r.attempt_no,
        'memory_id': str(r.memory_id), 'memory_version': r.memory_version, 'memory_revision': r.memory_revision,
        'phase': r.phase, 'reason': r.reason,
        'still_exists': db.scalar(select(Memory.id).where(Memory.id == r.memory_id, Memory.user_id == user_id)) is not None}
        for r in rows], 'next_cursor': None}
