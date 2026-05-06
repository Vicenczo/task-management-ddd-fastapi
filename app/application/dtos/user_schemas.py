"""
User DTOs (Data Transfer Objects).

Three-schema pattern per entity:
  - UserCreate   : data the client sends when registering a new user.
  - UserUpdate   : data the client sends when updating an existing user
                   (all fields optional — PATCH semantics).
  - UserResponse : data returned to the client (never exposes password hash).

Pydantic v2 used throughout. EmailStr requires `pip install email-validator`.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.domain.models.value_objects import UserRole


# ---------------------------------------------------------------------------
# Shared config
# ---------------------------------------------------------------------------

class _UserBase(BaseModel):
    """Fields shared between Create and Update schemas."""

    email: EmailStr | None = None
    username: str | None = Field(
        default=None,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="Alphanumeric username; underscores and hyphens allowed.",
    )
    full_name: str | None = Field(default=None, max_length=150)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

class UserCreate(_UserBase):
    """
    Schema for creating a new user account.

    `password` is accepted in plain text here and must be hashed
    by the service layer before persisting.
    """

    email: EmailStr  # required on create
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_\-]+$")
    full_name: str = Field(default="", max_length=150)
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Plain-text password — will be hashed before storage.",
    )
    role: UserRole = UserRole.MEMBER

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        """Store emails in lowercase for consistent lookup."""
        return value.lower()


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

class UserUpdate(_UserBase):
    """
    Schema for updating an existing user (PATCH semantics).

    All fields are optional; only provided fields are applied.
    Password changes use a dedicated endpoint (not this schema).
    """

    role: UserRole | None = None
    is_active: bool | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return value.lower() if value else value


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class UserResponse(BaseModel):
    """
    Schema for user data returned to the client.

    Intentionally excludes `hashed_password` and other internal fields.
    """

    model_config = {"from_attributes": True}

    id: UUID
    email: EmailStr
    username: str
    full_name: str
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Minimal response (used in lists / embedded in other responses)
# ---------------------------------------------------------------------------

class UserSummary(BaseModel):
    """Lightweight user representation for embedding in other resources."""

    model_config = {"from_attributes": True}

    id: UUID
    username: str
    full_name: str
    role: UserRole