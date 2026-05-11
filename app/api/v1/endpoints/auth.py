"""
Auth endpoints: registration and login.

POST /auth/register — create account + return token
POST /auth/login    — OAuth2-compatible login (form data)
"""
from fastapi import APIRouter
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends

from app.api.dependencies import UserServiceDep
from app.application.dtos.user_dtos import TokenResponse, UserCreate, UserResponse
from app.application.exceptions import AuthenticationError, ConflictError
from fastapi import HTTPException, status

router = APIRouter()


@router.post(
    "/register",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(dto: UserCreate, service: UserServiceDep) -> dict:
    """Register a new user and return an access token."""
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
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    service: UserServiceDep = ...,
) -> TokenResponse:
    """
    OAuth2-compatible login endpoint.
    Swagger UI uses this for the 'Authorize' button.
    Note: OAuth2PasswordRequestForm uses 'username' field — we treat it as email.
    """
    try:
        _, token_response = await service.login(
            email=form_data.username,  # OAuth2 form calls it username
            password=form_data.password,
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_response