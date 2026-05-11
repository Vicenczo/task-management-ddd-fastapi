"""
Application-level exceptions.

These are domain/application errors that the API layer catches and converts
to appropriate HTTP responses. They carry no HTTP knowledge themselves.

main.py registers a global handler for AppError -> HTTP 400.
More specific subclasses allow finer-grained HTTP mapping in routes.
"""


class AppError(Exception):
    """
    Base class for all application-layer errors.
    Caught by the global exception handler in main.py -> HTTP 400.
    """


class NotFoundError(AppError):
    """Resource does not exist. Maps to HTTP 404."""


class ConflictError(AppError):
    """Unique constraint violation (duplicate email, slug, etc.). Maps to HTTP 409."""


class AuthenticationError(AppError):
    """Invalid credentials. Maps to HTTP 401."""


class AuthorizationError(AppError):
    """Caller lacks permission. Maps to HTTP 403."""


class ValidationError(AppError):
    """Business rule validation failed. Maps to HTTP 422."""