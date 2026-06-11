from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.domains.users.model import User

# Reads Bearer tokens from the Authorization header
bearer_scheme = HTTPBearer()

# Get the currently logged-in user from the JWT token
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    credential_exception = HTTPException(
        status_code = status.HTTP_401_UNAUTHORIZED, 
        detail = "Could not validate credentials",
    )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: str = payload.get("sub")
    except JWTError as exc: 
        raise credential_exception from exc
    if user_id is None:
        raise credential_exception
    user = db.get(User, int(user_id))
    if user is None:
        raise credential_exception
    return user
