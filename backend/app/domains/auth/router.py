from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.domains.auth.schemas import LoginRequest, TokenResponse
from app.domains.users.service import get_user_by_email

# Routes for authentication
router = APIRouter(prefix="/auth", tags=["Auth"])

# Log in and receive an access token
@router.post("/login", response_model=TokenResponse)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    # Find the user by email
    user = get_user_by_email(db, login_data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    # Verify the password
    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    # Create and return an access token
    access_token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=access_token)