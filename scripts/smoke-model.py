"""Explicit opt-in live smoke, creates labelled synthetic sessions in local dev DB.

Run with backend/.venv/Scripts/python.exe scripts/smoke-model.py --live.
Calls the running local API; secrets are never printed or written to this script.
"""
import argparse
import json
import secrets
from pathlib import Path
import time
import uuid

import httpx


ANSWERS = {
    'technical': '浏览器先检查缓存，必要时解析 DNS，再建立 TCP 与 TLS 连接并发起 HTTP 请求。收到 HTML 后构建 DOM，解析 CSS 构建 CSSOM，合成渲染树，再布局、绘制与合成。脚本可能阻塞解析，CSS 可能阻塞渲染，缓存命中或连接复用会省掉部分网络步骤，不是每次都串行重做。可以用开发者工具的 Network 和 Performance 面板观察耗时。',
    'behavioral': '下面是专用于测试的虚构案例：课程小组做图书借阅系统，目标是让多人同时借书不超库存。我负责后端借阅接口，先复现并发问题，再与同学确认接口语义，使用条件更新与事务，补了两个并发请求的测试。最终演示中同一本库存为一的书只能有一个成功借出，另一请求返回库存不足。我只负责这个接口，没有声称负责整个系统。',
    'pressure': '下面是专用于测试的虚构案例：我会保留并发库存修复。在只有一周且不能重构全部服务的约束下，我选择数据库条件更新和事务，原因是能在一处保证扣减条件并由测试核对，而不是只靠前端禁用按钮。我用库存为一、两请求并发的实验观察到一成功一失败；这只是该场景的依据，不能证明所有高并发问题都已解决，也没有生产压测数据。',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Allow paid external model calls through local backend')
    parser.add_argument('--mode', choices=['all', *ANSWERS], default='all')
    args = parser.parse_args()
    if not args.live:
        parser.error('Explicit --live required. One session uses about 3 model calls, plus at most one repair per call.')
    root = Path(__file__).resolve().parents[1]
    runtime = root / '.runtime'
    runtime.mkdir(exist_ok=True)
    records = []
    with httpx.Client(base_url='http://127.0.0.1:8000/api/v1', timeout=15, trust_env=False) as client:
        def call(method, path, body=None, headers=None):
            response = client.request(method, path, json=body, headers=headers)
            if response.status_code >= 400:
                raise RuntimeError(f"{response.status_code}: {response.json().get('error', {}).get('code')}")
            return response.json()['data']
        identity = call('POST', '/identity', {'display_name': 'M3 合成场景验证'}, {'Idempotency-Key': secrets.token_hex(32)})
        auth = {'Authorization': 'Bearer ' + identity['token']}
        def post(path, body):
            return call('POST', path, body, {**auth, 'Idempotency-Key': uuid.uuid4().hex})
        def wait(oid):
            deadline = time.monotonic() + 190
            while time.monotonic() < deadline:
                result = call('GET', '/operations/' + oid, headers=auth)
                if result['status'] in {'succeeded', 'failed', 'cancelled'}:
                    if result['status'] != 'succeeded':
                        raise RuntimeError(result['error_code'] or result['status'])
                    return
                time.sleep(.5)
            raise RuntimeError('SMOKE_WAIT_TIMEOUT')
        for mode in (ANSWERS if args.mode == 'all' else [args.mode]):
            sid = None
            started = time.monotonic()
            try:
                session = post('/sessions', {'title': f'M3 合成验证 · {mode}', 'provider': 'deepseek', 'role': 'frontend', 'mode': mode,
                    'config': {'question_count': 1, 'max_followups': 0, 'pressure_consent': mode == 'pressure'}})
                sid = session['id']
                wait(post(f'/sessions/{sid}/actions', {'action': 'start', 'expected_version': session['version']})['operation_id'])
                session = call('GET', f'/sessions/{sid}', headers=auth)
                wait(post(f'/sessions/{sid}/messages', {'kind': 'answer', 'question_id': session['current_question']['id'],
                    'content': ANSWERS[mode], 'expected_version': session['version']})['operation_id'])
                report = call('GET', f'/sessions/{sid}/report', headers=auth)
                trace = call('GET', f'/sessions/{sid}/trace', headers=auth)
                assert report['status'] == 'ready' and not report['is_mock'] and report['coverage']['scored'] == 1
                assert len(report['question_evaluations']) == 1
                source = {m['id']: m for m in report['messages']}
                for q in report['question_evaluations']:
                    for dim in q['dimensions'].values():
                        for evidence in dim['evidence']:
                            msg = source[evidence['message_id']]
                            assert msg['speaker'] == 'user' and msg['kind'] == 'answer' and msg['question_id'] == q['question_id']
                            assert evidence['quote'] in msg['content']
                (runtime / f'm3-live-{mode}.json').write_text(json.dumps({'report': report, 'trace': trace}, ensure_ascii=False, indent=2), encoding='utf-8')
                def usage_sum(key):
                    values = [r['usage'][key] for r in trace['items']]
                    return sum(values) if all(v is not None for v in values) else None
                record = {'mode': mode, 'session_id': sid, 'status': 'passed', 'score': report['total_score'],
                    'dimensions': report['dimension_scores'], 'skills': sorted({r['skill_key'] for r in trace['items']}),
                    'calls': usage_sum('attempts'), 'input_tokens': usage_sum('input_tokens'),
                    'output_tokens': usage_sum('output_tokens'),
                    'seconds': round(time.monotonic() - started, 2)}
            except Exception as error:
                record = {'mode': mode, 'session_id': sid, 'status': 'failed', 'error': type(error).__name__,
                          'code': str(error) if isinstance(error, RuntimeError) else 'SMOKE_ASSERTION_FAILED'}
            records.append(record)
            print(json.dumps(record, ensure_ascii=False), flush=True)
    (runtime / 'm3-live-summary.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    if any(r['status'] != 'passed' for r in records):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
