"""
User endpoints.

GET    /users/me         — current user profile
PATCH  /users/me         — update current user profile
GET    /users/           — list all users
GET    /users/{user_id}  — fetch user by UUID

Route ordering: /me and / MUST precede /{user_id}.
Error handling delegated to global AppError handler.
"""
from uuid import UUID

from fastapi import APIRouter, status

from app.api.dependencies import CurrentUser, UserServiceDep
from app.application.dtos.user_dtos import UserResponse, UserUpdate

router = APIRouter()


@router.get("/me", response_model=UserResponse, summary="Get current user profile")
async def get_me(current_user: CurrentUser) -> UserResponse:
    """Returns the profile of the currently authenticated user."""
    return UserResponse.model_validate(current_user, from_attributes=True)


@router.patch("/me", response_model=UserResponse, summary="Update current user profile")
async def update_me(
    dto: UserUpdate,
    current_user: CurrentUser,
    service: UserServiceDep,
) -> UserResponse:
    """
    Update name or password. Omit a field to leave it unchanged.

    Raises (handled globally):
        NotFoundError → 404
    """
    return await service.update_profile(current_user.id, dto)


@router.get("/", response_model=list[UserResponse], summary="List all users")
async def list_users(
    service: UserServiceDep,
    current_user: CurrentUser,
    limit: int = 100,
    offset: int = 0,
) -> list[UserResponse]:
    """Paginated list of all users. Used to look up IDs for project membership."""
    return await service.list_users(limit=limit, offset=offset)


@router.get("/{user_id}", response_model=UserResponse, summary="Get user by ID")
async def get_user(
    user_id: UUID,
    service: UserServiceDep,
    current_user: CurrentUser,
) -> UserResponse:
    """
    Fetch any user by UUID.

    Raises (handled globally):
        NotFoundError → 404
    """
    return await service.get_by_id(user_id)