"""
Auth endpoints: registration and login.

POST /auth/register — create account + return token
POST /auth/login    — OAuth2-compatible login (form data)

Design notes:
  - /register returns both user data and token so the client
    can immediately authenticate without a second login call.
  - /login uses OAuth2PasswordRequestForm for Swagger UI compatibility.
    The 'username' field in the form is treated as email address.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencies import UserServiceDep
from app.application.dtos.user_dtos import TokenResponse, UserCreate
from app.application.exceptions import AuthenticationError, ConflictError

router = APIRouter()


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    response_description="Created user data with JWT access token",
)
async def register(dto: UserCreate, service: UserServiceDep) -> dict:
    """
    Register a new user.

    Returns the user profile and an access token so the client
    can immediately start making authenticated requests.
    """
    try:
        user_response, token_response = await service.register(dto)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
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
    OAuth2-compatible login endpoint used by Swagger UI 'Authorize' button.

    IMPORTANT: The OAuth2 form field is named 'username' but accepts an email address.
    Enter your email in the 'username' field when using Swagger UI.
    """
    try:
        _, token_response = await service.login(
            email=form_data.username,  # OAuth2 form field name is always 'username'
            password=form_data.password,
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_response