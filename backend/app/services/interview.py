import base64
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, tuple_

from app.agent.state_machine import ACTIVE, configuration_state, require_action
from app.core.errors import AppError
from app.models import Evaluation, InterviewSession, Message, Operation, OperationEvent, Profile, Question, Report, SkillRun
from app.schemas.profile import ProfileRead
from app.services.idempotency import begin_request, save_receipt


def now():
    return datetime.now(timezone.utc)


def owned_session(db, user_id, session_id, lock=False):
    query = select(InterviewSession).where(InterviewSession.id == session_id, InterviewSession.user_id == user_id)
    session = db.scalar(query.with_for_update() if lock else query)
    if session is None:
        raise AppError(404, 'RESOURCE_NOT_FOUND', '面试不存在或不属于当前身份')
    return session


def owned_operation(db, user_id, operation_id):
    operation = db.scalar(select(Operation).where(Operation.id == operation_id, Operation.user_id == user_id))
    if operation is None:
        raise AppError(404, 'RESOURCE_NOT_FOUND', '操作不存在或不属于当前身份')
    return operation


def active_operation(db, session_id):
    return db.scalar(select(Operation).where(Operation.session_id == session_id, Operation.status.in_(ACTIVE)))


def latest_operation(db, session_id):
    return db.scalar(select(Operation).where(Operation.session_id == session_id).order_by(Operation.created_at.desc(), Operation.id.desc()).limit(1))


def operation_data(db, operation):
    seq = db.scalar(select(func.max(OperationEvent.seq)).where(OperationEvent.operation_id == operation.id)) or 0
    return {'id': str(operation.id), 'session_id': str(operation.session_id), 'kind': operation.kind,
            'status': operation.status, 'attempt_no': operation.attempt_no, 'last_event_seq': seq,
            'cancel_requested': operation.cancel_requested, 'error_code': operation.error_code,
            'retryable': operation.status in {'failed', 'cancelled'}, 'result_refs': operation.result_refs}


def message_data(message):
    return {'id': str(message.id), 'seq': message.seq, 'speaker': message.speaker, 'kind': message.kind,
            'content': message.content, 'question_id': str(message.question_id) if message.question_id else None,
            'operation_id': str(message.operation_id) if message.operation_id else None,
            'created_at': message.created_at.isoformat()}


def coverage(db, session):
    questions = db.scalars(select(Question).where(Question.session_id == session.id)).all()
    answered = set(db.scalars(select(Message.question_id).where(Message.session_id == session.id,
                            Message.speaker == 'user', Message.kind == 'answer')).all())
    return {'planned': session.config['question_count'], 'asked': len(questions), 'answered': len(answered),
            'skipped': sum(q.status == 'skipped' for q in questions),
            'not_reached': max(0, session.config['question_count'] - len(questions)),
            'scored': db.scalar(select(func.count()).select_from(Evaluation).where(Evaluation.session_id == session.id,
                Evaluation.scope == 'final', Evaluation.question_score.is_not(None))) or 0}


def session_data(db, session):
    latest = latest_operation(db, session.id)
    question = db.get(Question, session.current_question_id) if session.current_question_id else None
    return {'id': str(session.id), 'title': session.title, 'role': session.role, 'mode': session.mode,
            'status': session.status, 'config': session.config, 'version': session.version,
            'is_mock': session.provider == 'mock', 'provider': session.provider, 'model_name': session.model_name,
            'rubric_version': session.rubric_version, 'prompt_version': session.prompt_version,
            'created_at': session.created_at.isoformat(),
            'current_question': {'id': str(question.id), 'ordinal': question.ordinal, 'topic': question.topic,
                                 'content': question.content, 'followup_count': question.followup_count,
                                 'hint_used': question.hint_used, 'difficulty': question.difficulty} if question else None,
            'active_operation_id': str(latest.id) if latest and latest.status in ACTIVE else None,
            'latest_operation': operation_data(db, latest) if latest else None, 'coverage': coverage(db, session)}


def ensure_version(session, expected):
    if session.version != expected:
        raise AppError(409, 'VERSION_CONFLICT', '会话已变化，请刷新后继续', {'current_version': session.version})


def ensure_idle(db, session):
    if active_operation(db, session.id):
        raise AppError(409, 'SESSION_BUSY', '当前生成尚未结束，请等待或停止生成')


def append_message(db, session_id, speaker, kind, content, question_id=None, operation_id=None):
    seq = (db.scalar(select(func.max(Message.seq)).where(Message.session_id == session_id)) or 0) + 1
    message = Message(session_id=session_id, speaker=speaker, kind=kind, content=content,
                      question_id=question_id, operation_id=operation_id, seq=seq)
    db.add(message)
    db.flush()
    return message


def create_session(db, user_id, body, key, settings=None):
    payload = body.model_dump(mode='json')
    receipt, key_hash, digest = begin_request(db, user_id, key, 'POST', '/api/v1/sessions', payload)
    if receipt:
        return receipt.response_data
    if body.provider == 'deepseek' and (settings is None or not settings.llm_api_key or not settings.llm_api_key.get_secret_value().strip()):
        raise AppError(503, 'MODEL_NOT_CONFIGURED', '真实模式需要后端本地 API Key，不会回退到 Mock')
    session = InterviewSession(user_id=user_id, title=body.title.strip() or '我的模拟面试', role=body.role,
                               mode=body.mode, config=body.config.model_dump(), status=configuration_state(body.role, body.mode), provider=body.provider)
    if body.provider == 'deepseek':
        from app.services.scoring import PROMPT_VERSION, RUBRIC_VERSION
        session.model_name, session.model_base_url = settings.llm_model, settings.llm_base_url
        session.prompt_version, session.rubric_version = PROMPT_VERSION, RUBRIC_VERSION
    db.add(session)
    db.flush()
    result = session_data(db, session)
    save_receipt(db, user_id, key_hash, digest, result)
    db.commit()
    return result


def patch_session(db, user_id, session_id, body, key):
    payload = body.model_dump(mode='json', exclude_unset=True)
    receipt, key_hash, digest = begin_request(db, user_id, key, 'PATCH', f'/api/v1/sessions/{session_id}', payload)
    if receipt:
        return receipt.response_data
    session = owned_session(db, user_id, session_id, True)
    ensure_version(session, body.expected_version)
    ensure_idle(db, session)
    if session.status not in {'clarifying', 'ready'}:
        raise AppError(409, 'INVALID_STATE', '开始后不能改写本次面试配置')
    for field, value in payload.items():
        if field != 'expected_version':
            setattr(session, field, body.config.model_dump() if field == 'config' else value)
    session.status = configuration_state(session.role, session.mode)
    session.version += 1
    db.flush()
    result = session_data(db, session)
    save_receipt(db, user_id, key_hash, digest, result)
    db.commit()
    return result


def submit(db, user_id, session_id, body, key, is_message=False):
    path = f'/api/v1/sessions/{session_id}/' + ('messages' if is_message else 'actions')
    payload = body.model_dump(mode='json')
    receipt, key_hash, digest = begin_request(db, user_id, key, 'POST', path, payload)
    if receipt:
        return receipt.response_data
    session = owned_session(db, user_id, session_id, True)
    ensure_version(session, body.expected_version)
    ensure_idle(db, session)
    action = body.kind if is_message else body.action
    require_action(session.status, action)
    if action == 'start':
        if session.mode == 'pressure' and not session.config['pressure_consent']:
            raise AppError(409, 'PRESSURE_CONSENT_REQUIRED', '请先确认压力训练强度与退出方式')
        profile = db.scalar(select(Profile).where(Profile.user_id == user_id))
        session.profile_snapshot = ProfileRead.model_validate(profile).model_dump(mode='json')
    if action in {'answer', 'hint', 'skip'}:
        if session.current_question_id is None:
            raise AppError(409, 'INVALID_STATE', '尚无可回答的问题，请重试首题生成')
        if is_message and str(body.question_id) != str(session.current_question_id):
            raise AppError(409, 'QUESTION_MISMATCH', '只能回答当前问题')
        unresolved = db.scalar(select(Operation.id).where(Operation.session_id == session.id, Operation.kind == 'answer',
            Operation.status.in_({'failed', 'cancelled'}),
            Operation.request_payload['question_id'].astext == str(session.current_question_id)).limit(1))
        if action == 'answer' and unresolved:
            raise AppError(409, 'OPERATION_RETRY_REQUIRED', '原答案已保存，请重试原操作，不要再次提交答案')
        if action == 'hint' and (db.get(Question, session.current_question_id).hint_used or db.scalar(select(Message.id).where(Message.question_id == session.current_question_id, Message.kind == 'hint').limit(1))):
            raise AppError(409, 'HINT_ALREADY_USED', '本题已经提供过提示')
    if action in {'pause', 'resume', 'abort', 'lower_pressure'}:
        if action == 'lower_pressure':
            if session.mode != 'pressure' or body.pressure_level is None or body.pressure_level >= session.config['pressure_level']:
                raise AppError(409, 'INVALID_STATE', '压力强度只能下调')
            session.config = {**session.config, 'pressure_level': body.pressure_level}
        else:
            session.status = {'pause': 'paused', 'resume': 'interviewing', 'abort': 'aborted'}[action]
        session.version += 1
        append_message(db, session.id, 'system', 'notice', {'pause': '面试已暂停。', 'resume': '面试已恢复。',
                       'abort': '本次配置已取消。', 'lower_pressure': '压力强度已降低。'}[action])
        result = {'session_id': str(session.id), 'session_version': session.version, 'operation_id': None, 'status': session.status}
    else:
        session.version += 1
        if action == 'finish':
            session.status = 'evaluating'
        operation = Operation(user_id=user_id, session_id=session.id, kind=action, key_hash=key_hash,
                              request_payload={**payload, 'question_id': str(session.current_question_id) if session.current_question_id else None},
                              expected_session_version=session.version)
        db.add(operation)
        db.flush()
        if is_message:
            message = append_message(db, session.id, 'user', action, body.content,
                                     session.current_question_id if action == 'answer' else None, operation.id)
            operation.request_payload = {**operation.request_payload, 'message_id': str(message.id)}
        result = {'session_id': str(session.id), 'session_version': session.version,
                  'operation_id': str(operation.id), 'status': 'queued'}
    save_receipt(db, user_id, key_hash, digest, result)
    db.commit()
    return result


def encode_cursor(value):
    return base64.urlsafe_b64encode(json.dumps(value).encode()).decode()


def decode_cursor(value):
    try:
        if len(value) > 512:
            raise ValueError()
        return json.loads(base64.urlsafe_b64decode(value))
    except Exception:
        raise AppError(400, 'INVALID_CURSOR', '列表游标无效') from None


def list_sessions(db, user_id, limit, cursor=None, status=None):
    query = select(InterviewSession).where(InterviewSession.user_id == user_id)
    if status:
        query = query.where(InterviewSession.status == status)
    if cursor:
        try:
            created, identifier = decode_cursor(cursor)
            query = query.where(tuple_(InterviewSession.created_at, InterviewSession.id) < tuple_(datetime.fromisoformat(created), uuid.UUID(identifier)))
        except (ValueError, TypeError):
            raise AppError(400, 'INVALID_CURSOR', '列表游标无效') from None
    rows = db.scalars(query.order_by(InterviewSession.created_at.desc(), InterviewSession.id.desc()).limit(limit + 1)).all()
    selected = rows[:limit]
    return {'items': [session_data(db, row) for row in selected],
            'next_cursor': encode_cursor([selected[-1].created_at.isoformat(), str(selected[-1].id)]) if len(rows) > limit else None}


def list_messages(db, user_id, session_id, limit, cursor=None):
    owned_session(db, user_id, session_id)
    after = decode_cursor(cursor) if cursor else 0
    if type(after) is not int or after < 0:
        raise AppError(400, 'INVALID_CURSOR', '消息游标无效')
    rows = db.scalars(select(Message).where(Message.session_id == session_id, Message.seq > after).order_by(Message.seq).limit(limit + 1)).all()
    return {'items': [message_data(row) for row in rows[:limit]],
            'next_cursor': encode_cursor(rows[limit - 1].seq) if len(rows) > limit else None}


def report_data(db, user_id, session_id):
    session = owned_session(db, user_id, session_id)
    report = db.scalar(select(Report).where(Report.session_id == session_id))
    if report is None:
        latest = latest_operation(db, session_id)
        return {'status': 'failed' if latest and latest.status == 'failed' else 'pending', 'is_mock': session.provider == 'mock',
                'total_score': None, 'coverage': coverage(db, session)}
    return {'id': str(report.id), 'session_id': str(session_id), 'status': report.status, 'is_mock': report.is_mock,
            'total_score': float(report.total_score) if report.total_score is not None else None,
            'summary': report.summary, 'coverage': report.coverage, 'dimension_scores': report.dimension_scores,
            'weights': report.weights, 'strengths': report.strengths, 'gaps': report.gaps, 'recommendations': report.recommendations,
            'provider': report.provider, 'model_name': report.model_name, 'rubric_version': report.rubric_version,
            'prompt_version': report.prompt_version, 'question_evaluations': evaluations_for_report(db, session_id),
            'messages': [message_data(m) for m in db.scalars(select(Message).where(Message.session_id == session_id).order_by(Message.seq)).all()]}


def evaluations_for_report(db, session_id):
    from app.agent.orchestrator import evaluation_data
    rows = db.scalars(select(Evaluation).where(Evaluation.session_id == session_id, Evaluation.scope == 'final').order_by(Evaluation.created_at)).all()
    result = []
    for row in rows:
        question = db.get(Question, row.question_id)
        result.append({**evaluation_data(row), 'question': question.content, 'ordinal': question.ordinal,
                       'topic': question.topic, 'hint_used': question.hint_used})
    return result


def trace_data(db, user_id, session_id):
    owned_session(db, user_id, session_id)
    return {'items': [{'id': str(r.id), 'skill_key': r.skill_key, 'skill_version': r.skill_version,
        'phase': r.phase, 'status': r.status, 'provider': r.provider, 'model_name': r.model_name,
        'attempt_no': r.attempt_no, 'usage': r.usage, 'error_code': r.error_code,
        'input_refs': r.input_refs} for r in db.scalars(select(SkillRun).where(SkillRun.session_id == session_id).order_by(SkillRun.created_at)).all()],
        'next_cursor': None}


def delete_session(db, user_id, session_id, expected_version, key):
    payload = {'expected_version': expected_version}
    receipt, key_hash, digest = begin_request(db, user_id, key, 'DELETE', f'/api/v1/sessions/{session_id}', payload)
    if receipt:
        return
    session = owned_session(db, user_id, session_id, True)
    ensure_version(session, expected_version)
    ensure_idle(db, session)
    session.current_question_id = None
    db.flush()
    db.execute(delete(InterviewSession).where(InterviewSession.id == session_id))
    save_receipt(db, user_id, key_hash, digest, {'deleted': str(session_id)})
    db.commit()
