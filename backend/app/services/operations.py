import json
import logging
import time
import traceback
import uuid
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from sqlalchemy import func, select, text

from app.agent.state_machine import ACTIVE, TERMINAL, configuration_state, require_action
from app.core.errors import AppError
from app.llm.mock import MockProvider
from app.models import Evaluation, InterviewSession, Message, Operation, OperationEvent, Question, Report
from app.services.idempotency import begin_request, save_receipt
from app.services.interview import (
    append_message, coverage, ensure_idle, now, operation_data, owned_operation, owned_session,
)


def add_event(db, operation, event_type, payload):
    seq = (db.scalar(select(func.max(OperationEvent.seq)).where(OperationEvent.operation_id == operation.id)) or 0) + 1
    db.add(OperationEvent(operation_id=operation.id, seq=seq, attempt_no=operation.attempt_no,
                          event_type=event_type, payload={**payload, 'attempt_no': operation.attempt_no}))
    operation.heartbeat_at = now()


def control_operation(db, user_id, operation_id, key, retry=False):
    action = 'retry' if retry else 'cancel'
    receipt, key_hash, digest = begin_request(db, user_id, key, 'POST', f'/api/v1/operations/{operation_id}/{action}', {})
    if receipt:
        return receipt.response_data
    operation = owned_operation(db, user_id, operation_id)
    session = owned_session(db, user_id, operation.session_id, True)
    operation = db.scalar(select(Operation).where(Operation.id == operation_id).with_for_update().execution_options(populate_existing=True))
    if retry:
        if operation.status not in {'failed', 'cancelled'}:
            raise AppError(409, 'INVALID_STATE', '只有失败或取消的操作可以重试')
        ensure_idle(db, session)
        if operation.kind == 'finish':
            if session.status != 'evaluating':
                raise AppError(409, 'INVALID_STATE', '该总结操作已不适用')
        else:
            require_action(session.status, operation.kind)
        question_id = operation.request_payload.get('question_id')
        if operation.kind in {'answer', 'hint', 'skip'} and question_id != str(session.current_question_id):
            raise AppError(409, 'QUESTION_MISMATCH', '该操作已不对应当前问题')
        session.version += 1
        operation.expected_session_version = session.version
        operation.attempt_no += 1
        operation.status = 'queued'
        operation.cancel_requested = False
        operation.error_code = None
        operation.finished_at = None
        operation.result_refs = {}
    elif operation.status in ACTIVE:
        operation.cancel_requested = True
    result = operation_data(db, operation)
    save_receipt(db, user_id, key_hash, digest, result)
    db.commit()
    return result


class OperationRunner:
    """Single-process executor; database facts survive, in-flight computation does not."""
    LOCK_ID = 73640201

    def __init__(self, engine, factory, delay=0.04, settings=None):
        self.engine, self.factory, self.delay = engine, factory, delay
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='talentgo-operation')
        self.provider = MockProvider()
        self.real = None
        if settings is not None:
            from app.agent.orchestrator import RealInterviewOrchestrator
            self.real = RealInterviewOrchestrator(settings, factory)
        self.lock_connection = None

    def start(self):
        self.lock_connection = self.engine.connect()
        if not self.lock_connection.execute(text('SELECT pg_try_advisory_lock(:key)'), {'key': self.LOCK_ID}).scalar():
            self.lock_connection.close()
            self.executor.shutdown()
            raise RuntimeError('TalentGo supports one backend process per database')
        self.lock_connection.commit()
        # Allow health endpoints to explain a missing migration, rather than create tables implicitly.
        with self.engine.connect() as connection:
            exists = connection.execute(text("SELECT to_regclass('public.operations')")).scalar()
        if exists:
            self.recover_interrupted()

    def recover_interrupted(self):
        with self.factory() as db:
            rows = db.scalars(select(Operation).where(Operation.status.in_(ACTIVE)).with_for_update()).all()
            for operation in rows:
                operation.status = 'failed'
                operation.error_code = 'PROCESS_INTERRUPTED'
                operation.finished_at = now()
                add_event(db, operation, 'operation.failed', {'error_code': operation.error_code, 'retryable': True})
            db.commit()

    def stop(self):
        self.executor.shutdown(wait=True, cancel_futures=False)
        if self.lock_connection is not None:
            self.lock_connection.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': self.LOCK_ID})
            self.lock_connection.commit()
            self.lock_connection.close()

    def submit(self, operation_id, attempt_no):
        self.executor.submit(self.run, uuid.UUID(str(operation_id)), attempt_no)

    def _locked(self, db, operation_id):
        reference = db.get(Operation, operation_id)
        if reference is None:
            return None, None
        session = db.scalar(select(InterviewSession).where(InterviewSession.id == reference.session_id).with_for_update())
        operation = db.scalar(select(Operation).where(Operation.id == operation_id).with_for_update().execution_options(populate_existing=True))
        return session, operation

    def _cancelled(self, db, session, operation):
        if operation.cancel_requested:
            operation.status = 'cancelled'
            operation.finished_at = now()
            add_event(db, operation, 'operation.cancelled', {'session_id': str(session.id)})
            return True
        return False

    def plan(self, db, session, operation):
        kind = operation.kind
        if kind in {'clarify', 'clarification'}:
            role, mode = session.role, session.mode
            if kind == 'clarification':
                content = operation.request_payload['content'].lower()
                front = '前端' in content or 'frontend' in content
                back = '后端' in content or 'backend' in content
                if not role and front != back:
                    role = 'frontend' if front else 'backend'
                modes = [name for name, token in [('technical', '技术'), ('behavioral', '行为'), ('pressure', '压力')]
                         if token in content or name in content]
                if not mode and len(modes) == 1:
                    mode = modes[0]
            missing = []
            if not role:
                missing.append('岗位：前端 / 后端')
            if not mode:
                missing.append('面试类型：技术 / 行为 / 压力')
            content = ('请补充 ' + '；'.join(missing) + '。也可以直接点击页面中的选项。') if missing else '目标已确认。请检查配置后点击「开始面试」。'
            return {'type': 'clarification', 'text': content, 'role': role, 'mode': mode}
        question = db.get(Question, session.current_question_id) if session.current_question_id else None
        if kind == 'hint':
            return {'type': 'hint', 'text': self.provider.hint()}
        if kind == 'answer':
            followup = self.provider.followup(operation.request_payload['content'], question.followup_count, session.config['max_followups'])
            if followup:
                return {'type': 'followup', 'text': followup}
        ordinal = (question.ordinal + 1) if question else 1
        if kind == 'finish' or ordinal > session.config['question_count']:
            return {'type': 'report', 'text': '本次 Mock 训练已结束，正在整理实际问答与完成情况。此阶段不生成能力分数。'}
        topic, content = self.provider.question(session.role, session.mode, ordinal)
        return {'type': 'question', 'ordinal': ordinal, 'topic': topic, 'text': content}

    def commit_plan(self, db, session, operation, plan):
        kind = plan['type']
        question = db.get(Question, session.current_question_id) if session.current_question_id else None
        for entry in plan.get('evaluations', []):
            revision = (db.scalar(select(func.max(Evaluation.revision)).where(Evaluation.question_id == uuid.UUID(entry['question_id']))) or 0) + 1
            db.add(Evaluation(session_id=session.id, question_id=uuid.UUID(entry['question_id']), operation_id=operation.id,
                revision=revision, scope=entry['scope'], dimensions=entry['dimensions'], missing_points=entry['missing_points'],
                suggestion=entry['suggestion'], flag=entry['flag'],
                question_score=Decimal(str(entry['question_score'])) if entry['question_score'] is not None else None,
                context_hash=entry['context_hash'], rubric_version=session.rubric_version, prompt_version=session.prompt_version,
                provider=session.provider, model_name=session.model_name))
        if kind == 'clarification':
            session.role, session.mode = plan['role'], plan['mode']
            session.status = configuration_state(session.role, session.mode)
            append_message(db, session.id, 'assistant', 'clarification', plan['text'], operation_id=operation.id)
        elif kind in {'hint', 'followup'}:
            if kind == 'followup':
                question.followup_count += 1
            if kind == 'hint' or plan.get('uses_hint'):
                question.hint_used = True
            append_message(db, session.id, 'assistant', kind, plan['text'], question.id, operation.id)
        else:
            if question and operation.kind == 'skip':
                question.status = 'skipped'
                append_message(db, session.id, 'system', 'notice', '本题已跳过。', question.id, operation.id)
            elif question:
                has_answer = db.scalar(select(Message.id).where(Message.question_id == question.id, Message.kind == 'answer').limit(1))
                question.status = 'answered' if has_answer else 'unscored'
            if kind == 'question':
                next_question = Question(session_id=session.id, ordinal=plan['ordinal'], topic=plan['topic'], content=plan['text'],
                                         difficulty=plan.get('difficulty', session.config['difficulty']),
                                         source_key=plan.get('source_key'), rubric_snapshot=plan.get('rubric_snapshot', {}))
                db.add(next_question)
                db.flush()
                session.current_question_id = next_question.id
                session.status = 'interviewing'
                session.started_at = session.started_at or now()
                append_message(db, session.id, 'assistant', 'question', plan['text'], next_question.id, operation.id)
            else:
                db.flush()
                counts = coverage(db, session)
                summary = (f"本次计划 {counts['planned']} 题，已提问 {counts['asked']} 题，"
                           f"实际回答 {counts['answered']} 题，跳过 {counts['skipped']} 题，"
                           f"未到达 {counts['not_reached']} 题。以上为问答记录统计。"
                           '当前为固定规则 Mock 演示，尚未评估回答质量，不提供能力分数或录用判断。')
                if session.provider == 'deepseek':
                    from app.services.scoring import WEIGHTS
                    review = plan['review']
                    db.add(Report(session_id=session.id, coverage=counts, summary=review['summary'], is_mock=False,
                        provider=session.provider, model_name=session.model_name, rubric_version=session.rubric_version,
                        prompt_version=session.prompt_version, total_score=Decimal(str(plan['total_score'])) if plan['total_score'] is not None else None,
                        dimension_scores=plan['dimension_scores'], weights=WEIGHTS[session.mode],
                        strengths=review['strengths'], gaps=review['gaps'], recommendations=review['recommendations']))
                else:
                    db.add(Report(session_id=session.id, coverage=counts, summary=summary))
                session.status = 'completed'
                session.ended_at = now()
                append_message(db, session.id, 'assistant', 'notice', plan['text'], operation_id=operation.id)
        session.version += 1
        operation.status = 'succeeded'
        operation.finished_at = now()
        operation.result_refs = {'session_id': str(session.id), 'session_version': session.version,
                                 'report_ready': session.status == 'completed'}
        add_event(db, operation, 'state.changed', {'status': session.status, 'session_version': session.version})
        add_event(db, operation, 'operation.succeeded', operation.result_refs)

    def run(self, operation_id, attempt_no):
        try:
            with self.factory() as db:
                session, operation = self._locked(db, operation_id)
                if not operation or operation.attempt_no != attempt_no or operation.status != 'queued':
                    return
                if self._cancelled(db, session, operation):
                    db.commit()
                    return
                operation.status = 'running'
                add_event(db, operation, 'operation.started', {'operation_id': str(operation.id), 'is_mock': session.provider == 'mock'})
                real_snapshot = None
                if session.provider == 'deepseek':
                    from app.agent.orchestrator import snapshot_for_model
                    real_snapshot = snapshot_for_model(db, session, operation)
                else:
                    plan = self.plan(db, session, operation)
                db.commit()
            # External I/O must never retain the row locks / Session used for acceptance.
            if real_snapshot is not None:
                if self.real is None:
                    raise AppError(503, 'MODEL_NOT_CONFIGURED', '真实模型执行器未配置')
                plan = self.real.plan(real_snapshot)
            for offset in range(0, len(plan['text']), 12):
                time.sleep(self.delay)
                with self.factory() as db:
                    session, operation = self._locked(db, operation_id)
                    if not operation or operation.attempt_no != attempt_no or operation.status != 'running':
                        return
                    if self._cancelled(db, session, operation):
                        db.commit()
                        return
                    add_event(db, operation, 'text.delta', {'channel': plan['type'], 'text': plan['text'][offset:offset + 12]})
                    db.commit()
            with self.factory() as db:
                session, operation = self._locked(db, operation_id)
                if not operation or operation.attempt_no != attempt_no or operation.status != 'running':
                    return
                if self._cancelled(db, session, operation):
                    db.commit()
                    return
                if session.version != operation.expected_session_version:
                    raise AppError(409, 'VERSION_CONFLICT', '生成期间会话发生变化')
                self.commit_plan(db, session, operation, plan)
                db.commit()
        except Exception as error:
            frames = traceback.extract_tb(error.__traceback__)
            locations = [(frame.name, frame.lineno) for frame in frames if '/app/' in frame.filename.replace('\\', '/')]
            logging.getLogger(__name__).error('Operation failure type=%s sqlstate=%s location=%s',
                type(error).__name__, getattr(getattr(error, 'orig', None), 'sqlstate', None), locations)
            self.fail(operation_id, attempt_no, error.code if isinstance(error, AppError) else 'WORKER_FAILED')

    def fail(self, operation_id, attempt_no, code):
        with self.factory() as db:
            session, operation = self._locked(db, operation_id)
            if operation and operation.attempt_no == attempt_no and operation.status in ACTIVE:
                if self._cancelled(db, session, operation):
                    db.commit()
                    return
                operation.status = 'failed'
                operation.error_code = code
                operation.finished_at = now()
                add_event(db, operation, 'operation.failed', {'error_code': code, 'retryable': True})
                db.commit()


def validate_event_cursor(db, user_id, operation_id, last_event_id):
    operation = owned_operation(db, user_id, operation_id)
    if operation.finished_at and operation.finished_at < now() - timedelta(days=7):
        raise AppError(410, 'EVENT_HISTORY_EXPIRED', '事件已超出重放期限，请读取会话快照')
    after = 0
    if last_event_id:
        try:
            identifier, raw_seq = last_event_id.rsplit(':', 1)
            after = int(raw_seq)
            if uuid.UUID(identifier) != operation_id or after < 0 or after > operation_data(db, operation)['last_event_seq']:
                raise ValueError()
        except (ValueError, TypeError):
            raise AppError(400, 'INVALID_EVENT_CURSOR', '事件游标无效或不属于当前操作') from None
    return after


def event_stream(factory, operation_id, after):
    heartbeat = time.monotonic()
    while True:
        with factory() as db:
            operation = db.get(Operation, operation_id)
            if operation is None:
                return
            rows = db.scalars(select(OperationEvent).where(OperationEvent.operation_id == operation_id,
                              OperationEvent.seq > after).order_by(OperationEvent.seq).limit(100)).all()
            items = [(row.seq, row.event_type, row.payload) for row in rows]
            terminal = operation.status in TERMINAL
        for seq, event_type, payload in items:
            after = seq
            yield f'id: {operation_id}:{seq}\nevent: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n'
        if terminal and len(items) < 100:
            return
        if time.monotonic() - heartbeat > 10:
            yield ': heartbeat\n\n'
            heartbeat = time.monotonic()
        time.sleep(0.1)
