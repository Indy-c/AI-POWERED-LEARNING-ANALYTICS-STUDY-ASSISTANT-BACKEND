from passlib.context import CryptContext

# Password hashing configuration
password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Convert plain password to hashed password
def hash_password(password: str) -> str:
    return password_context.hash(password)

# Check a plain password against a stored hashed password
def verify_password(password: str, hashed_password: str) -> bool:
    return password_context.verify(password, hashed_password)