import json

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.core.errors import AppError
from app.llm.deepseek import DeepSeekProvider
from app.schemas.evaluation import GeneratedHint


def settings(**values):
    return Settings(_env_file=None, database_url=SecretStr('postgresql+psycopg://fixture:fixture@localhost:6543/fixture_test'),
                    llm_api_key=SecretStr('fixture-key'), **values)


def stream(content, usage=True, finish='stop', reasoning=False):
    delta = {'content': content}
    if reasoning:
        delta['reasoning_content'] = 'INTERNAL_NOT_TO_STORE'
    events = [{'choices': [{'delta': delta, 'finish_reason': finish}]}]
    if usage:
        events.append({'choices': [], 'usage': {'prompt_tokens': 11, 'completion_tokens': 7}})
    data = ''.join('data: ' + json.dumps(e, ensure_ascii=False) + '\n\n' for e in events) + 'data: [DONE]\n\n'
    return httpx.Response(200, headers={'content-type': 'text/event-stream'}, content=data.encode())


def invoke(handler, check=lambda: None, validate=None, **values):
    return DeepSeekProvider(settings(**values), transport=httpx.MockTransport(handler)).generate(
        GeneratedHint, '只输出 JSON', {}, check, validate)


def test_stream_request_and_usage_ignore_reasoning():
    def handler(request):
        body = json.loads(request.content)
        assert body['stream'] and body['response_format'] == {'type': 'json_object'}
        assert body['thinking'] == {'type': 'disabled'}
        assert body['stream_options']['include_usage']
        return stream('{"hint":"先说明事务的原子性。"}', reasoning=True)
    result = invoke(handler)
    assert result.value.hint == '先说明事务的原子性。'
    assert result.input_tokens == 11 and result.output_tokens == 7 and result.attempts == 1
    assert 'INTERNAL' not in result.value.model_dump_json()


@pytest.mark.parametrize('status,code', [(401, 'MODEL_AUTH_FAILED'), (402, 'MODEL_BALANCE_REQUIRED'),
    (429, 'MODEL_RATE_LIMITED'), (500, 'MODEL_UNAVAILABLE'), (307, 'MODEL_UNAVAILABLE')])
def test_http_errors_no_fallback_or_secret(status, code):
    with pytest.raises(AppError) as error:
        invoke(lambda _: httpx.Response(status, text='fixture-key backend error'))
    assert error.value.code == code
    assert 'fixture-key' not in str(error.value)


def test_one_repair_and_usage():
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        return stream('bad json' if len(calls) == 1 else '{"hint":"先解释事务的原子性。"}')
    result = invoke(handler)
    assert len(calls) == 2 and result.attempts == 2
    assert result.input_tokens == 22 and result.output_tokens == 14
    assert len(calls[1]['messages']) == 4


def test_unknown_usage_not_fabricated_on_repair():
    calls = []
    def handler(_):
        calls.append(1)
        return stream('bad' if len(calls) == 1 else '{"hint":"先解释事务的原子性。"}', usage=len(calls) > 1)
    result = invoke(handler)
    assert result.input_tokens is None and result.output_tokens is None


@pytest.mark.parametrize('body,finish', [('bad json', 'stop'), ('{"hint":"先解释事务的原子性。"}', 'length'),
    ('{"hint":"先解释事务的原子性。","total_score":100}', 'stop')])
def test_invalid_or_truncated_output_only_repairs_once(body, finish):
    calls = []
    def handler(_):
        calls.append(1)
        return stream(body, finish=finish)
    with pytest.raises(AppError) as error:
        invoke(handler)
    assert error.value.code == 'MODEL_OUTPUT_INVALID' and len(calls) == 2


def test_semantic_validator_repairs_then_rejects():
    def invalid(value):
        raise ValueError('not a source quote')
    with pytest.raises(AppError) as error:
        invoke(lambda _: stream('{"hint":"先解释事务的原子性。"}'), validate=invalid)
    assert error.value.code == 'MODEL_OUTPUT_INVALID'


@pytest.mark.parametrize('response', [httpx.Response(200, json={'hint': '非流式'}),
    httpx.Response(200, headers={'content-type': 'text/event-stream'}, text='data: {oops}\n\n'),
    httpx.Response(200, headers={'content-type': 'text/event-stream'}, text='data: []\n\n')])
def test_bad_protocol(response):
    with pytest.raises(AppError) as error:
        invoke(lambda _: response)
    assert error.value.code == 'MODEL_PROTOCOL_ERROR'


def test_timeout_and_cancellation():
    def timeout(_):
        raise httpx.ReadTimeout('sensitive upstream text')
    with pytest.raises(AppError) as error:
        invoke(timeout)
    assert error.value.code == 'MODEL_TIMEOUT'
    calls = []
    def check():
        calls.append(1)
        if len(calls) >= 2:
            raise AppError(409, 'OPERATION_CANCELLED', '停止')
    with pytest.raises(AppError) as cancelled:
        invoke(lambda _: stream('{"hint":"先解释事务的原子性。"}'), check=check)
    assert cancelled.value.code == 'OPERATION_CANCELLED'
