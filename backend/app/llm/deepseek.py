import json
import time
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from app.core.errors import AppError
from app.llm.base import ModelResult


class DeepSeekProvider:
    """Bounded Chat Completions JSON adapter; reasoning content is never stored."""
    def __init__(self, settings, model=None, base_url=None, transport=None):
        self.settings = settings
        self.model = model or settings.llm_model
        self.base_url = base_url or settings.llm_base_url
        self.transport = transport

    def generate(self, schema, system, context, check, validate=None):
        key = self.settings.llm_api_key
        if not key or not key.get_secret_value().strip():
            raise AppError(503, 'MODEL_NOT_CONFIGURED', '请先在后端本地环境配置模型 API Key')
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        messages = [{'role': 'system', 'content': system + '\n必须只输出 JSON 对象，严格满足以下 schema，不增加字段：\n' + schema_json},
                    {'role': 'user', 'content': json.dumps({'untrusted_material': context}, ensure_ascii=False)}]
        started = time.monotonic()
        tokens_in, tokens_out = 0, 0
        complete_usage = True
        first_content_ms = None
        cache_hit, cache_miss, complete_cache = 0, 0, True
        for attempt in range(2):
            request_usage = None
            request_cache = None
            check()
            if sum(len(m['content']) for m in messages) > self.settings.context_max_characters:
                raise AppError(422, 'CONTEXT_TOO_LONG', '上下文过长，请缩短输入或新建练习；当前答案未截断评分')
            payload = {'model': self.model, 'messages': messages, 'response_format': {'type': 'json_object'},
                       'stream': True, 'max_tokens': self.settings.llm_max_tokens, 'temperature': 0.2,
                       'stream_options': {'include_usage': True}}
            if urlsplit(self.base_url).hostname in {'api.deepseek.com'}:
                payload['thinking'] = {'type': 'disabled'}
            content = ''
            finish_reason = None
            try:
                timeout = httpx.Timeout(connect=10, read=min(15, self.settings.llm_timeout_seconds), write=10, pool=5)
                with httpx.Client(timeout=timeout, transport=self.transport, follow_redirects=False) as client:
                    with client.stream('POST', self.base_url + '/chat/completions',
                                       headers={'Authorization': 'Bearer ' + key.get_secret_value()}, json=payload) as response:
                        if response.status_code != 200:
                            codes = {401: 'MODEL_AUTH_FAILED', 402: 'MODEL_BALANCE_REQUIRED', 429: 'MODEL_RATE_LIMITED'}
                            raise AppError(503, codes.get(response.status_code, 'MODEL_UNAVAILABLE'), '模型服务请求失败，请检查密钥、余额、限额或服务配置')
                        if 'text/event-stream' not in response.headers.get('content-type', ''):
                            raise AppError(503, 'MODEL_PROTOCOL_ERROR', '模型服务未返回兼容的流式响应')
                        for line in response.iter_lines():
                            check()
                            if time.monotonic() - started > self.settings.llm_timeout_seconds:
                                raise AppError(503, 'MODEL_TIMEOUT', '模型生成超过本次时间预算')
                            if not line.startswith('data:'):
                                continue
                            data = line[5:].strip()
                            if data == '[DONE]':
                                break
                            try:
                                event = json.loads(data)
                                choices = event.get('choices', [])
                                if choices:
                                    delta = choices[0].get('delta', {}).get('content') or ''
                                    if delta and first_content_ms is None:
                                        first_content_ms = int((time.monotonic() - started) * 1000)
                                    content += delta
                                    finish_reason = choices[0].get('finish_reason') or finish_reason
                                usage = event.get('usage')
                                if usage:
                                    request_usage = (int(usage['prompt_tokens']), int(usage['completion_tokens']))
                                    if any(n<0 for n in request_usage):raise ValueError('Negative usage')
                                    if usage.get('prompt_cache_hit_tokens') is not None and usage.get('prompt_cache_miss_tokens') is not None:
                                        hit,miss=int(usage['prompt_cache_hit_tokens']),int(usage['prompt_cache_miss_tokens'])
                                        if hit>=0 and miss>=0 and hit+miss==request_usage[0]:request_cache=(hit,miss)
                            except (ValueError, TypeError, KeyError, AttributeError, IndexError):
                                raise AppError(503, 'MODEL_PROTOCOL_ERROR', '模型事件结构不合法') from None
                            if len(content) > 32000:
                                raise AppError(503, 'MODEL_OUTPUT_INVALID', '模型输出超过结构化结果上限')
            except httpx.TimeoutException:
                raise AppError(503, 'MODEL_TIMEOUT', '模型连接或读取超时；不会静默改用 Mock') from None
            except httpx.HTTPError:
                raise AppError(503, 'MODEL_UNAVAILABLE', '无法连接模型服务；不会静默改用 Mock') from None
            check()
            if request_usage is not None:
                tokens_in += request_usage[0]
                tokens_out += request_usage[1]
            else:
                complete_usage = False
            if request_cache is not None:
                cache_hit+=request_cache[0];cache_miss+=request_cache[1]
            else:complete_cache=False
            try:
                if finish_reason not in {'stop'}:
                    raise ValueError('Output was incomplete or truncated')
                value = schema.model_validate_json(content)
                if validate:
                    validate(value)
                return ModelResult(value, tokens_in if complete_usage else None, tokens_out if complete_usage else None,
                                   int((time.monotonic() - started) * 1000), attempt + 1, first_content_ms,
                                   cache_hit if complete_cache else None,cache_miss if complete_cache else None)
            except (ValidationError, ValueError):
                if attempt:
                    raise AppError(503, 'MODEL_OUTPUT_INVALID', '模型结果或证据校验失败，已进行一次修复；没有计入成绩') from None
                messages += [{'role': 'assistant', 'content': content[:16000]},
                             {'role': 'user', 'content': '上次结果未通过结构或原文引用校验。请重新输出完整 JSON；所有非空分数必须引用允许的用户答案 ID 和逐字原文。不得增加总分或不存在的来源。'}]
        raise AppError(503, 'MODEL_OUTPUT_INVALID', '模型结果不可用')
