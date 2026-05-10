"""
ORM model for the users table.

Maps to domain entity: app.domain.models.user.User

Design decisions:
  - email and username have unique indexes — enforced at DB level, not just domain.
  - role is stored as VARCHAR (StrEnum serializes to its string value).
  - hashed_password is never None in DB (empty string only during seeding/testing).
"""
from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models.base import Base


class UserModel(Base):
    """PostgreSQL table: users."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("username", name="uq_users_username"),
    )

    # --- Identity ---
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    # --- Auth ---
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # --- Role & Status ---
    # Stored as plain string — matches StrEnum.value (e.g. "admin", "member", "viewer")
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="member")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return f"UserModel(id={self.id!s:.8}..., username='{self.username}', role='{self.role}')"