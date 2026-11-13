import json
import re
from app.core.errors import AppError
from app.services.interview import report_data, owned_session

LABELS={'relevance':'切题程度','accuracy_consistency':'准确与一致性','reasoning':'分析与推理','evidence_detail':'证据与细节','communication':'表达沟通'}


def plain(value):
    # Inert fenced text keeps user material from becoming active HTML/Markdown.
    text=str(value)
    fence='`'*max(3,max([len(x) for x in re.findall(r'`+',text)] or [0])+1)
    return f'{fence}text\n{text}\n{fence}'


def export_report(db,user_id,sid,format):
    data=report_data(db,user_id,sid)
    if data['status']!='ready':raise AppError(409,'REPORT_NOT_READY','报告尚未生成，无法导出')
    session=owned_session(db,user_id,sid)
    exported={'export_version':'1.0','title':session.title,'role':session.role,'mode':session.mode,
        'notice':'仅供训练参考；Mock 不是能力评分。分数不核实经历、不诊断心理、不预测录用。',**data}
    if format=='json':return json.dumps(exported,ensure_ascii=False,indent=2),'application/json'
    lines=['# TalentGo 训练报告',plain(session.title),'来源：',plain('Mock · 固定规则，不计能力分' if data['is_mock'] else data['model_name']),
        f"模式：{session.role} / {session.mode}",f"Prompt：{data.get('prompt_version')}；rubric：{data.get('rubric_version')}",
        exported['notice'],f"总分：{data['total_score'] if data['total_score'] is not None else '未计分'} / 100",'## 完成覆盖']
    lines += [f'- {key}: {value}' for key,value in data['coverage'].items()]
    lines += ['## 复盘摘要',plain(data['summary']),'## 维度分（0—5，缺失不是零）']
    lines += [f"- {label}: {data['dimension_scores'].get(key) if data['dimension_scores'].get(key) is not None else '材料不足'}；权重 {data['weights'].get(key,'—')}" for key,label in LABELS.items()]
    for name,title in [('strengths','表现亮点'),('gaps','待补充'),('recommendations','建议')]:
        lines.append('## '+title)
        for item in data[name]:lines += [plain(item['text']), '来源题目：'+', '.join(item['question_ids'])]
    for q in data['question_evaluations']:
        lines += [f"## 第 {q['ordinal']} 题 · {q['topic']}",plain(q['question']),
            f"题分：{q['question_score'] if q['question_score'] is not None else '未计分'}；提示：{'使用过' if q['hint_used'] else '未使用'}"]
        for key,d in q['dimensions'].items():
            lines += [f"### {LABELS[key]}：{d['score'] if d['score'] is not None else '材料不足'}",plain(d['reason'])]
            for e in d['evidence']: lines += ['原文消息：'+e['message_id'],plain(e['quote'])]
        lines += ['缺口：',plain('；'.join(q['missing_points'])),'建议：',plain(q['suggestion'])]
    lines.append('## 完整正式问答')
    for message in data['messages']:
        lines += [f"### {message['seq']} · {message['speaker']} · {message['kind']} · {message['id']}",plain(message['content'])]
    return '\n\n'.join(lines)+'\n','text/markdown'
