from pydantic import BaseModel, EmailStr

# Data needed to log in
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

# Token returned after successful login
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"