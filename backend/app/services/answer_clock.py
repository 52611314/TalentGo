from datetime import timedelta
from math import ceil


def start_turn(question, config, timestamp):
    seconds = config.get('answer_time_seconds', 0)
    question.answer_deadline_at = timestamp + timedelta(seconds=seconds) if seconds else None
    question.answer_remaining_ms = None


def pause_turn(question, timestamp):
    if question.answer_deadline_at is not None:
        question.answer_remaining_ms = max(0, ceil((question.answer_deadline_at - timestamp).total_seconds() * 1000))
        question.answer_deadline_at = None


def resume_turn(question, timestamp):
    if question.answer_remaining_ms is not None:
        question.answer_deadline_at = timestamp + timedelta(milliseconds=question.answer_remaining_ms)
        question.answer_remaining_ms = None


def turn_expired(question, timestamp):
    return question.answer_deadline_at is not None and question.answer_deadline_at <= timestamp
