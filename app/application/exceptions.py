"""
Application-layer exceptions.

These exceptions are raised by service classes and caught by API route
handlers, which map them to appropriate HTTP responses.

Hierarchy:
    AppError                    ← base for all application errors
    ├── NotFoundError           ← 404
    ├── ConflictError           ← 409  (duplicate email, slug, etc.)
    ├── PermissionDeniedError   ← 403
    ├── ValidationError         ← 422  (business-rule violation)
    └── AuthenticationError     ← 401

Design rule: never import FastAPI or HTTP status codes here.
The API layer is responsible for the HTTP mapping.
"""


class AppError(Exception):
    """Base class for all application-layer errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.message!r})"


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""


class ConflictError(AppError):
    """Raised when an operation would violate a uniqueness constraint."""


class PermissionDeniedError(AppError):
    """Raised when the caller lacks permission to perform an action."""


class ValidationError(AppError):
    """Raised when input passes schema validation but violates a business rule."""


class AuthenticationError(AppError):
    """Raised when credentials are missing or invalid."""