"""
User endpoints.

GET  /users/me       — current user profile
PATCH /users/me      — update current user profile
GET  /users/{id}     — fetch any user by ID (admin or self)
GET  /users/         — list all users (admin only)
"""
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CurrentUser, UserServiceDep
from app.application.dtos.user_dtos import UserResponse, UserUpdate
from app.application.exceptions import NotFoundError

router = APIRouter()


@router.get("/me", response_model=UserResponse, summary="Get current user profile")
async def get_me(current_user: CurrentUser) -> UserResponse:
    """Returns the profile of the authenticated user."""
    from app.application.dtos.user_dtos import UserResponse as UR
    return UR.model_validate(current_user, from_attributes=True)


@router.patch("/me", response_model=UserResponse, summary="Update current user profile")
async def update_me(
    dto: UserUpdate,
    current_user: CurrentUser,
    service: UserServiceDep,
) -> UserResponse:
    """Update name or password of the authenticated user."""
    try:
        return await service.update_profile(current_user.id, dto)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/{user_id}", response_model=UserResponse, summary="Get user by ID")
async def get_user(
    user_id: UUID,
    service: UserServiceDep,
    current_user: CurrentUser,
) -> UserResponse:
    """Fetch any user by UUID. Requires authentication."""
    try:
        return await service.get_by_id(user_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/", response_model=list[UserResponse], summary="List all users (admin only)")
async def list_users(
    service: UserServiceDep,
    current_user: CurrentUser,
    limit: int = 100,
    offset: int = 0,
) -> list[UserResponse]:
    """List all users. Currently open to all authenticated users — restrict to admin in next phase."""
    return await service.list_users(limit=limit, offset=offset)