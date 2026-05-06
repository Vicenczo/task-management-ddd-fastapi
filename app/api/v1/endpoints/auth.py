"""
Authentication endpoints.

POST /auth/token  — OAuth2 password flow (login, returns JWT).
GET  /auth/me     — Return the currently authenticated user's profile.
"""
from fastapi import APIRouter, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from fastapi import Depends

from app.api.dependencies import CurrentUser, UserServiceDep
from app.application.exceptions import AuthenticationError
from app.core.security import create_access_token
from app.application.dtos.user_schemas import UserResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


# ---------------------------------------------------------------------------
# Schemas local to this module (OAuth2 token shape is standardized)
# ---------------------------------------------------------------------------

from pydantic import BaseModel


class TokenResponse(BaseModel):
    """Standard OAuth2 token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Login — obtain a JWT access token",
    description=(
        "Submit credentials using the OAuth2 **password** flow. "
        "The returned `access_token` must be sent as a `Bearer` token "
        "in the `Authorization` header on subsequent requests."
    ),
)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    user_service: UserServiceDep,
) -> TokenResponse:
    """
    Authenticate with email (username field) + password.

    FastAPI's OAuth2PasswordRequestForm uses `username` as the field name
    by spec — we treat it as the email address.
    """
    try:
        user = await user_service.verify_credentials(
            email=form_data.username,
            password=form_data.password,
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )

    from app.core.config import settings
    token = create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user",
)
async def get_me(current_user: CurrentUser) -> UserResponse:
    """Return the profile of the currently authenticated user."""
    return UserResponse.model_validate(current_user, from_attributes=True)