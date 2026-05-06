"""
User Application Service.

Orchestrates use cases related to user management:
  - Registration with duplicate detection
  - Profile retrieval and updates
  - Role management
  - Account activation / deactivation

The service layer is the only place allowed to call both the repository
and domain entity methods in the same transaction. It must not contain
SQL, HTTP, or serialization logic.
"""
from uuid import UUID

from app.application.dtos.user_schemas import UserCreate, UserResponse, UserUpdate
from app.application.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.domain.models.user import User
from app.domain.models.value_objects import UserRole
from app.domain.repository_interfaces import AbstractUserRepository


class UserService:
    """
    Application service for User use cases.

    Receives a repository through the constructor (Dependency Inversion).
    The session / transaction is managed one layer up (FastAPI dependency).
    """

    def __init__(self, user_repo: AbstractUserRepository) -> None:
        self._users = user_repo

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_password(plain: str) -> str:
        """
        Hash a plain-text password using bcrypt.

        Imported lazily to avoid loading passlib at module import time.
        """
        from passlib.context import CryptContext
        _ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return _ctx.hash(plain)

    @staticmethod
    def _verify_password(plain: str, hashed: str) -> bool:
        from passlib.context import CryptContext
        _ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return _ctx.verify(plain, hashed)

    async def _get_or_raise(self, user_id: UUID) -> User:
        """Fetch a user by ID or raise NotFoundError."""
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User with id '{user_id}' not found.")
        return user

    # ------------------------------------------------------------------
    # Use cases
    # ------------------------------------------------------------------

    async def register(self, data: UserCreate) -> UserResponse:
        """
        Register a new user account.

        Steps:
          1. Check email and username uniqueness.
          2. Hash the password.
          3. Persist the new User entity.
          4. Return the response DTO.
        """
        if await self._users.exists_by_email(data.email):
            raise ConflictError(f"Email '{data.email}' is already registered.")
        if await self._users.exists_by_username(data.username):
            raise ConflictError(f"Username '{data.username}' is already taken.")

        user = User(
            email=data.email,
            username=data.username,
            full_name=data.full_name,
            hashed_password=self._hash_password(data.password),
            role=data.role,
        )
        await self._users.add(user)
        return UserResponse.model_validate(user, from_attributes=True)

    async def get_by_id(self, user_id: UUID) -> UserResponse:
        """Return a user profile by primary key."""
        user = await self._get_or_raise(user_id)
        return UserResponse.model_validate(user, from_attributes=True)

    async def get_by_email(self, email: str) -> UserResponse:
        """Return a user profile by email address."""
        user = await self._users.get_by_email(email)
        if user is None:
            raise NotFoundError(f"No user found with email '{email}'.")
        return UserResponse.model_validate(user, from_attributes=True)

    async def list_users(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[UserResponse]:
        """Return a paginated list of all users."""
        users = await self._users.list_all(limit=limit, offset=offset)
        return [UserResponse.model_validate(u, from_attributes=True) for u in users]

    async def update(self, user_id: UUID, data: UserUpdate) -> UserResponse:
        """
        Apply a partial update to an existing user.

        Only fields explicitly provided (non-None) are applied.
        """
        user = await self._get_or_raise(user_id)

        if data.email is not None and data.email != user.email:
            if await self._users.exists_by_email(data.email):
                raise ConflictError(f"Email '{data.email}' is already in use.")
            user.email = data.email

        if data.username is not None and data.username != user.username:
            if await self._users.exists_by_username(data.username):
                raise ConflictError(f"Username '{data.username}' is already taken.")
            user.username = data.username

        if data.full_name is not None:
            user.full_name = data.full_name

        if data.role is not None:
            try:
                user.change_role(data.role)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc

        if data.is_active is not None:
            try:
                if data.is_active:
                    user.activate()
                else:
                    user.deactivate()
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc

        user.touch()
        await self._users.update(user)
        return UserResponse.model_validate(user, from_attributes=True)

    async def change_password(
        self,
        user_id: UUID,
        *,
        current_password: str,
        new_password: str,
    ) -> None:
        """
        Change a user's password after verifying the current one.

        Raises:
            ValidationError: If current_password doesn't match.
        """
        user = await self._get_or_raise(user_id)
        if not self._verify_password(current_password, user.hashed_password):
            raise ValidationError("Current password is incorrect.")
        if len(new_password) < 8:
            raise ValidationError("New password must be at least 8 characters.")
        user.hashed_password = self._hash_password(new_password)
        user.touch()
        await self._users.update(user)

    async def promote_to_admin(self, user_id: UUID) -> UserResponse:
        """Promote a user to the ADMIN role."""
        user = await self._get_or_raise(user_id)
        try:
            user.promote_to_admin()
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        await self._users.update(user)
        return UserResponse.model_validate(user, from_attributes=True)

    async def deactivate(self, user_id: UUID) -> UserResponse:
        """Deactivate a user account."""
        user = await self._get_or_raise(user_id)
        try:
            user.deactivate()
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        await self._users.update(user)
        return UserResponse.model_validate(user, from_attributes=True)

    async def activate(self, user_id: UUID) -> UserResponse:
        """Re-activate a previously deactivated user account."""
        user = await self._get_or_raise(user_id)
        try:
            user.activate()
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        await self._users.update(user)
        return UserResponse.model_validate(user, from_attributes=True)

    async def verify_credentials(self, email: str, password: str) -> User:
        """
        Verify login credentials and return the User domain entity.

        Used exclusively by AuthService — returns raw entity, not DTO.

        Raises:
            AuthenticationError: If email not found or password is wrong.
        """
        from app.application.exceptions import AuthenticationError
        user = await self._users.get_by_email(email)
        if user is None or not self._verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid email or password.")
        if not user.is_active:
            raise AuthenticationError("This account has been deactivated.")
        return user

    async def delete(self, user_id: UUID) -> None:
        """Permanently delete a user account."""
        await self._get_or_raise(user_id)  # Ensure exists before deleting
        await self._users.delete(user_id)