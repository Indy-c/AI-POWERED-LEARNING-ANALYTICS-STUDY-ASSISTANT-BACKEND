from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.domains.users.model import User
from app.domains.users.schemas import UserCreate

# Find one user by email address to check if the email is already registered.
def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()

# Create and save a new user
def create_user(db: Session, user_data: UserCreate) -> User:
    db_user = User(
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=hash_password(user_data.password),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user