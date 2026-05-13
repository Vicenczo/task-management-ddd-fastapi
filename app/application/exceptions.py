"""
Application-level exceptions.

Each exception class carries an http_status_code attribute.
The global exception handler in main.py reads this to produce
the correct HTTP response — endpoints never import HTTPException.

Hierarchy:
    AppError (base, 400)
    ├── NotFoundError       → 404
    ├── ConflictError       → 409
    ├── AuthenticationError → 401
    ├── AuthorizationError  → 403
    └── ValidationError     → 422
"""
from http import HTTPStatus


class AppError(Exception):
    """
    Base class for all application-layer errors.

    Subclasses set http_status_code to control the HTTP response.
    Falls back to 400 Bad Request if not overridden.
    """

    http_status_code: int = HTTPStatus.BAD_REQUEST  # 400


class NotFoundError(AppError):
    """Resource does not exist."""

    http_status_code: int = HTTPStatus.NOT_FOUND  # 404


class ConflictError(AppError):
    """Unique constraint violation (duplicate email, slug, etc.)."""

    http_status_code: int = HTTPStatus.CONFLICT  # 409


class AuthenticationError(AppError):
    """Invalid credentials or missing/expired token."""

    http_status_code: int = HTTPStatus.UNAUTHORIZED  # 401


class AuthorizationError(AppError):
    """Caller is authenticated but lacks permission."""

    http_status_code: int = HTTPStatus.FORBIDDEN  # 403


class ValidationError(AppError):
    """Business rule validation failed (not Pydantic schema validation)."""

    http_status_code: int = HTTPStatus.UNPROCESSABLE_ENTITY  # 422