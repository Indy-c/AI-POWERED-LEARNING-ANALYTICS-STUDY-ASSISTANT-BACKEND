from fastapi import APIRouter, Request, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.domains.users.schemas import UserCreate, UserRead
from app.domains.users.service import get_user_by_email, create_user
from app.domains.auth.dependencies import get_current_user
from app.domains.users.model import User

# Routes for user account management
router = APIRouter(prefix="/users", tags=["Users"])

# Register a new user account
@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")  # Example: limit to 5 registration attempts per minute per IP
def register_user(request: Request, user_data: UserCreate, db: Session = Depends(get_db)):
    # Check if the email is already registered
    existing_user = get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered",
        )
    return create_user(db, user_data)

# Get the current user's profile
@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user