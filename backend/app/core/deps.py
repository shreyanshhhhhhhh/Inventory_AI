import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db import get_db
from app.models import User
from app.repositories.users import get_user_by_id

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Sign in is required.")
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Access token is expired.") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Access token is invalid.") from exc

    user_id = payload.get("sub")
    business_id = payload.get("business_id")
    if not isinstance(user_id, str) or not isinstance(business_id, str):
        raise HTTPException(status_code=401, detail="Access token is invalid.")

    user = get_user_by_id(db, user_id)
    if user is None or not user.is_active or user.business_id != business_id:
        raise HTTPException(status_code=401, detail="Sign in is required.")
    return user


def require_owner(user: User = Depends(get_current_user)) -> User:
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="Owner access is required.")
    return user
