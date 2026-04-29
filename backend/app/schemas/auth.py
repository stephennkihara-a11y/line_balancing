from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

from ..models.user import UserRole


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    username: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None
    role: UserRole = UserRole.IE


class UserOut(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    full_name: str | None
    role: UserRole
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
