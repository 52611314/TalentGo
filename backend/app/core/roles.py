import json
import math
from pathlib import Path
from typing import Annotated
from pydantic import AfterValidator, StringConstraints

ROLES = json.loads((Path(__file__).resolve().parents[1] / 'knowledge/roles.json').read_text(encoding='utf-8'))
ROLE_BY_ID = {item['id']: item for item in ROLES}


def validate_role(value):
    if value not in ROLE_BY_ID:
        raise ValueError('Unknown target role')
    return value


Role = Annotated[str, StringConstraints(max_length=32), AfterValidator(validate_role)]


def role_plan(primary, config):
    if not primary:
        return []
    secondary = config.get('secondary_roles', [])
    total = config['question_count']
    if not secondary:
        return [{'role': primary, 'question_count': total, 'primary': True}]
    main_count = min(math.ceil(total * .6), total - len(secondary))
    remaining = total - main_count
    return [{'role': primary, 'question_count': main_count, 'primary': True}] + [
        {'role': role, 'question_count': remaining // len(secondary) + (i < remaining % len(secondary)), 'primary': False}
        for i, role in enumerate(secondary)]


def role_for_question(primary, config, ordinal):
    for item in role_plan(primary, config):
        ordinal -= item['question_count']
        if ordinal <= 0:
            return item['role']
    raise ValueError('Question ordinal outside the role plan')


def validate_selection(primary, config):
    secondary = config.get('secondary_roles', [])
    if len(set(secondary)) != len(secondary) or primary in secondary:
        raise ValueError('岗位不能重复')
    if secondary and (not primary or config['question_count'] < len(secondary) + 2):
        raise ValueError('选择次选岗位时须明确主岗位，且题数至少为岗位数加一')
