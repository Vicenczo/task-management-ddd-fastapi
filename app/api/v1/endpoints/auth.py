"""
Auth endpoints.

POST /auth/register — create account + return token
POST /auth/login    — OAuth2-compatible login (form data)

Error handling is delegated to the global AppError handler in main.py.
These functions raise domain exceptions; the handler converts them to HTTP.
"""
from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencies import UserServiceDep
from app.application.dtos.user_dtos import TokenResponse, UserCreate

router = APIRouter()


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    response_description="Created user data with JWT access token",
)
async def register(dto: UserCreate, service: UserServiceDep) -> dict:
    """
    Register a new user and return an access token.

    Raises (handled globally):
        ConflictError → 409 if email or username already exists.
    """
    user_response, token_response = await service.register(dto)
    return {
        "user": user_response.model_dump(),
        "token": token_response.model_dump(),
    }


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive a JWT access token",
    response_description="JWT bearer token",
)
async def login(
    service: UserServiceDep,
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> TokenResponse:
    """
    OAuth2-compatible login.

    IMPORTANT: Enter your email address in the 'username' field in Swagger UI.

    Raises (handled globally):
        AuthenticationError → 401 if credentials are invalid.
    """
    _, token_response = await service.login(
        email=form_data.username,
        password=form_data.password,
    )
    return token_response