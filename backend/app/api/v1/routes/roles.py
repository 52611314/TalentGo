from fastapi import APIRouter, Query, Request
from app.api.deps import response
from app.core.roles import ROLES

router = APIRouter(prefix='/roles', tags=['roles'])


@router.get('')
def roles(request: Request, q: str = Query(default='', max_length=100)):
    keywords = q.casefold().split()
    selected = [r for r in ROLES if all(k in ' '.join([r['label'], r['id'], r['group'], r['focus'], *r['aliases']]).casefold() for k in keywords)]
    return response(request, {'items': selected, 'total': len(ROLES), 'max_roles': 3})
