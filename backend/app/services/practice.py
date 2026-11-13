from sqlalchemy import select
from app.core.errors import AppError
from app.models import Evaluation, InterviewSession, Memory, PracticeTask, Question, Report, SessionSummary
from app.services.memory import invalidate, profile_lock


def task_data(row):
    from app.services.scoring import RUBRIC_VERSION
    return {'id': str(row.id), 'source_session_id': str(row.source_session_id),
        'source_evaluation_id': str(row.source_evaluation_id), 'role': row.role, 'mode': row.mode,
        'topic': row.topic, 'instruction': row.instruction, 'rubric_version': row.rubric_version,
        'status': row.status, 'can_practice': row.status == 'pending' and row.rubric_version == RUBRIC_VERSION,
        'version_supported': row.rubric_version == RUBRIC_VERSION, 'created_at': row.created_at.isoformat()}


def owned_task(db, user_id, tid):
    row = db.scalar(select(PracticeTask).where(PracticeTask.id == tid, PracticeTask.user_id == user_id))
    if row is None: raise AppError(404, 'RESOURCE_NOT_FOUND', '复练来源已删除或不属于当前身份')
    return row


def tasks(db, user_id, limit=20, offset=0, status=None):
    query = select(PracticeTask).where(PracticeTask.user_id == user_id)
    if status: query = query.where(PracticeTask.status == status)
    rows = db.scalars(query.order_by(PracticeTask.created_at.desc(), PracticeTask.id).offset(offset).limit(limit+1)).all()
    return {'items': [task_data(r) for r in rows[:limit]], 'next_offset': offset+limit if len(rows)>limit else None}


def validate_source(db, user_id, body):
    task = owned_task(db, user_id, body.source_task_id)
    if body.provider != 'deepseek' or body.role != task.role or body.mode != task.mode:
        raise AppError(422, 'TASK_CONFIG_MISMATCH', '复练须使用真实模型和来源任务相同的岗位/模式')
    from app.services.scoring import RUBRIC_VERSION
    if task.rubric_version != RUBRIC_VERSION or not task.seed:
        raise AppError(409, 'TASK_VERSION_UNSUPPORTED', '来源评分版本已变化，请建立普通练习')
    if task.status == 'completed': raise AppError(409, 'TASK_COMPLETED', '任务已完成')
    active = db.scalar(select(InterviewSession.id).where(InterviewSession.source_task_id == task.id,
        InterviewSession.status.not_in(['completed','aborted'])).limit(1))
    if active: raise AppError(409, 'TASK_IN_PROGRESS', '已有未结束复练，请从训练记录继续')
    task.status = 'in_progress'
    return task


def settle_task(db, session):
    if not session.source_task_id: return
    task = owned_task(db, session.user_id, session.source_task_id)
    valid = db.scalar(select(Evaluation.id).join(Question, Evaluation.question_id == Question.id).where(
        Evaluation.session_id == session.id, Evaluation.scope == 'final', Evaluation.question_score.is_not(None),
        Question.ordinal == 1, Question.topic == task.topic))
    if task.status != 'completed': task.status = 'completed' if valid else 'pending'


def derive(db, session):
    """Only validated final real evaluations produce tasks and opt-in memory candidates."""
    if session.provider != 'deepseek': return
    rows = db.scalars(select(Evaluation).where(Evaluation.session_id == session.id, Evaluation.scope == 'final',
        Evaluation.question_score.is_not(None))).all()
    profile = profile_lock(db, session.user_id)
    wrote_memory = False
    for row in rows:
        question = db.get(Question, row.question_id)
        weak = bool(row.missing_points) or any(d['score'] is not None and float(d['score']) < 3 for d in row.dimensions.values())
        if not weak: continue
        if not db.scalar(select(PracticeTask.id).where(PracticeTask.source_evaluation_id == row.id)):
            db.add(PracticeTask(user_id=session.user_id, source_session_id=session.id, source_evaluation_id=row.id,
                role=session.role, mode=session.mode, topic=question.topic, seed=question.rubric_snapshot,
                rubric_version=session.rubric_version, instruction=row.suggestion))
        existing = db.scalar(select(Memory.id).where(Memory.user_id == session.user_id, Memory.kind == 'weakness',
            Memory.topic == question.topic, Memory.role == session.role, Memory.mode == session.mode))
        if profile.allow_inferred_memory and not existing:
            db.add(Memory(user_id=session.user_id, kind='weakness', topic=question.topic, role=session.role, mode=session.mode,
                content=('待复查：' + '；'.join(row.missing_points or [row.suggestion]))[:1200],
                source_type='system_inferred', source_session_id=session.id, source_evaluation_id=row.id, confirmed=False))
            wrote_memory = True
    if wrote_memory: invalidate(db, profile)
    db.flush()
    settle_task(db, session)


def trends(db, user_id, limit=100, offset=0):
    # Keyset by chronological index is exposed as bounded offset for this local MVP.
    rows = db.execute(select(Report, InterviewSession).join(InterviewSession, Report.session_id == InterviewSession.id).where(
        InterviewSession.user_id == user_id, Report.is_mock.is_(False), Report.total_score.is_not(None))
        .order_by(Report.created_at, Report.id).offset(offset).limit(limit+1)).all()
    groups = {}
    for report, session in rows[:limit]:
        key = (session.role, session.mode, report.rubric_version)
        groups.setdefault(key, []).append({'session_id': str(session.id), 'score': float(report.total_score),
            'created_at': report.created_at.isoformat(), 'coverage': report.coverage, 'model_name': report.model_name,
            'prompt_version': report.prompt_version})
    return {'groups': [{'role': k[0], 'mode': k[1], 'rubric_version': k[2], 'points': v} for k,v in groups.items()],
        'next_offset': offset+limit if len(rows)>limit else None,
        'notice': '按岗位/模式/评分版本分组；题目、模型和提示使用可能不同，分数变化不等于能力提升。'}
