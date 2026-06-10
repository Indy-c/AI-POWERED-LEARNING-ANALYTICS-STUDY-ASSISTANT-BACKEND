from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
from .config import settings

# Password hashing configuration
password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Convert plain password to hashed password
def hash_password(password: str) -> str:
    return password_context.hash(password)

# Check a plain password against a stored hashed password
def verify_password(password: str, hashed_password: str) -> bool:
    return password_context.verify(password, hashed_password)

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