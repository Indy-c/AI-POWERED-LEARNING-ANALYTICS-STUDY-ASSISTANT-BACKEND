from datetime import datetime, timedelta, timezone
import bcrypt
from jose import jwt
from .config import settings

# Convert a plain password to a hashed password using bcrypt
def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    hashed_password = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed_password.decode("utf-8")

# Check a plain password against a stored hashed password
def verify_password(password: str, hashed_password: str) -> bool:
    password_bytes = password.encode("utf-8")
    hashed_password_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_password_bytes)

# Create a signed JWT access token for a user
def create_access_token(subject: str) -> str:
    expire_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": subject, "exp": expire_at}

    return jwt.encode(
        payload, 
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )