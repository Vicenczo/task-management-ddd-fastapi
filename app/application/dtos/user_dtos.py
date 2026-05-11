"""
User-related DTOs.

UserCreate  — incoming registration payload.
UserLogin   — incoming login payload (also used by OAuth2 form).
UserUpdate  — partial update (all fields optional).
UserResponse — outgoing representation (never includes password).
TokenResponse — JWT token pair returned after successful auth.
"""
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.domain.models.value_objects import UserRole


class UserCreate(BaseModel):
    """Registration request. Password is plain text here — hashed in UserService."""

    email: EmailStr
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    full_name: str = Field(default="", max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def username_lowercase(cls, v: str) -> str:
        return v.lower()


class UserLogin(BaseModel):
    """Login request. Maps to OAuth2PasswordRequestForm fields."""

    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """Partial update — all fields optional. None means 'do not change'."""

    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserResponse(BaseModel):
    """Outgoing user representation. Never exposes hashed_password."""

    model_config = {"from_attributes": True}

    id: UUID
    email: str
    username: str
    full_name: str
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    """JWT token pair returned after successful login/registration."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds