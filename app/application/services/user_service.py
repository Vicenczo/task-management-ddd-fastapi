"""
UserService — Application service for user lifecycle and authentication.

Responsibilities:
  - Register new users (hash password, check uniqueness).
  - Authenticate users (verify password, issue JWT).
  - Update user profile.
  - Never expose hashed passwords outside this service.

Uses:
  - passlib[bcrypt] for password hashing (in requirements.txt).
  - python-jose[cryptography] for JWT signing (in requirements.txt).
"""
import logging
from datetime import timedelta
from uuid import UUID

from jose import jwt
from passlib.context import CryptContext

from app.application.dtos.user_dtos import TokenResponse, UserCreate, UserResponse, UserUpdate
from app.application.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.core.config import settings
from app.domain.models.base import _utcnow
from app.domain.models.user import User
from app.domain.models.value_objects import UserRole
from app.domain.repository_interfaces import AbstractUserRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bcrypt Context Setup
# ---------------------------------------------------------------------------
# Napomena: bcrypt ima limit od 72 karaktera za lozinku.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash_password(plain: str) -> str:
    """
    Hashes a plain text password using bcrypt.

    CRITICAL: Bcrypt has a 72-byte limit. We truncate or validate
    to prevent ValueError from crashing the worker.
    """
    if not plain:
        raise ValueError("Password cannot be empty.")

    # Ako je lozinka predugačka, bcrypt će pući.
    # Ovde bacamo jasnu grešku pre nego što passlib pokuša heširanje.
    if len(plain) > 72:
        raise AuthenticationError("Password is too long. Maximum allowed length is 72 characters.")

    return _pwd_context.hash(plain)


def _verify_password(plain: str, hashed: str) -> bool:
    """Verifies a plain text password against its hash."""
    if not plain or not hashed:
        return False
    try:
        return _pwd_context.verify(plain, hashed)
    except Exception as e:
        logger.error("Password verification failed: %s", str(e))
        return False


def _create_access_token(user_id: UUID) -> tuple[str, int]:
    """
    Create a signed JWT access token.

    Returns:
        (encoded_token, expires_in_seconds)
    """
    expire_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    expire = _utcnow() + timedelta(seconds=expire_seconds)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": _utcnow(),
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, expire_seconds


class UserService:
    """
    Orchestrates user registration, authentication, and profile management.
    """

    def __init__(self, repository: AbstractUserRepository) -> None:
        self._repo = repository

    async def register(self, dto: UserCreate) -> tuple[UserResponse, TokenResponse]:
        """
        Register a new user.
        """
        if await self._repo.get_by_email(dto.email):
            raise ConflictError(f"Email '{dto.email}' is already registered.")
        if await self._repo.get_by_username(dto.username):
            raise ConflictError(f"Username '{dto.username}' is already taken.")

        # Heširanje sa ugrađenom provere dužine
        hashed = _hash_password(dto.password)

        user = User(
            email=dto.email,
            username=dto.username,
            full_name=dto.full_name,
            hashed_password=hashed,
            role=UserRole.MEMBER,
            is_active=True,
            is_verified=False,
        )
        saved = await self._repo.save(user)
        token, expires_in = _create_access_token(saved.id)

        logger.info("New user registered: id=%s, username=%s", saved.id, saved.username)
        return (
            UserResponse.model_validate(saved, from_attributes=True),
            TokenResponse(access_token=token, expires_in=expires_in),
        )

    async def login(self, email: str, password: str) -> tuple[UserResponse, TokenResponse]:
        """
        Authenticate a user by email + password.
        """
        user = await self._repo.get_by_email(email)

        # Provera postojanja i lozinke
        if user is None or not _verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid email or password.")

        if not user.is_active:
            raise AuthenticationError("Account is deactivated. Contact an administrator.")

        token, expires_in = _create_access_token(user.id)
        logger.info("User logged in: id=%s", user.id)
        return (
            UserResponse.model_validate(user, from_attributes=True),
            TokenResponse(access_token=token, expires_in=expires_in),
        )

    async def get_by_id(self, user_id: UUID) -> UserResponse:
        """Fetch a user by ID."""
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User with id={user_id} not found.")
        return UserResponse.model_validate(user, from_attributes=True)

    async def update_profile(
        self, user_id: UUID, dto: UserUpdate
    ) -> UserResponse:
        """Update user profile fields."""
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User with id={user_id} not found.")

        if dto.full_name is not None:
            user.full_name = dto.full_name
            user.touch()
        if dto.password is not None:
            user.hashed_password = _hash_password(dto.password)
            user.touch()

        updated = await self._repo.update(user)
        return UserResponse.model_validate(updated, from_attributes=True)

    async def list_users(self, *, limit: int = 100, offset: int = 0) -> list[UserResponse]:
        """Return paginated list of all users."""
        users = await self._repo.list_all(limit=limit, offset=offset)
        return [UserResponse.model_validate(u, from_attributes=True) for u in users]