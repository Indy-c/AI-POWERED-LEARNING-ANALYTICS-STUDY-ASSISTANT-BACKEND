from pydantic import BaseModel, EmailStr
from datetime import datetime

# Data needed to create a new user
class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str

# Data returned when fetching user details
class UserRead(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    role: str
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}

