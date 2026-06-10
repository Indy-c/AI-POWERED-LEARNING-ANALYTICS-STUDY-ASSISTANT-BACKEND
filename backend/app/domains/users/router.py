from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.users.schemas import UserCreate, UserRead
from app.domains.users.service import get_user_by_email, create_user

# Routes for user account management
router = APIRouter(prefix="/users", tags=["Users"])

# Register a new user account
@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    # Check if the email is already registered
    existing_user = get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered",
        )
    return create_user(db, user_data)