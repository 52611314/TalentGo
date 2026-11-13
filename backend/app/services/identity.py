from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import generate_token, hash_secret
from app.models import Profile, User
from app.schemas.profile import ProfileRead


def create_identity(db: Session, display_name: str, creation_key: str) -> dict:
    token = generate_token()
    user = User(display_name=display_name, token_hash=hash_secret(token), creation_key_hash=hash_secret(creation_key))
    try:
        db.add(user)
        db.flush()
        profile = Profile(user_id=user.id)
        db.add(profile)
        db.flush()
        data = {'user_id': str(user.id), 'display_name': user.display_name, 'token': token,
                'profile': ProfileRead.model_validate(profile).model_dump(mode='json')}
        db.commit()
        return data
    except IntegrityError:
        db.rollback()
        raise AppError(409, 'IDENTITY_ALREADY_CREATED', '此创建请求已完成；身份凭证不会重复签发') from None
