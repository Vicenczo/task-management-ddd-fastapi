"""
User management endpoints.

POST   /users/              — Register a new account (public).
GET    /users/              — List all users (admin only).
GET    /users/{user_id}     — Get a user profile.
PATCH  /users/{user_id}     — Update a user profile (self or admin).
DELETE /users/{user_id}     — Delete a user (admin only).
POST   /users/{user_id}/promote   — Promote user to admin (admin only).
POST   /users/{user_id}/deactivate — Deactivate account (self or admin).
POST   /users/{user_id}/activate   — Re-activate account (admin only).
POST   /users/me/change-password   — Change own password.
"""
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import CurrentUser, UserServiceDep
from app.application.dtos.user_schemas import UserCreate, UserResponse, UserUpdate
from app.application.exceptions import ConflictError, NotFoundError, ValidationError

router = APIRouter(prefix="/users", tags=["Users"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assert_self_or_admin(current_user: object, target_id: UUID) -> None:
    """Allow action only if caller is the target user or an admin."""
    from app.domain.models.user import User
    u: User = current_user  # type: ignore[assignment]
    if u.id != target_id and not u.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only modify your own account.",
        )


def _assert_admin(current_user: object) -> None:
    from app.domain.models.user import User
    u: User = current_user  # type: ignore[assignment]
    if not u.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    data: UserCreate,
    user_service: UserServiceDep,
) -> UserResponse:
    """
    Public endpoint — no authentication required.

    Creates a new user account with the MEMBER role by default.
    """
    try:
        return await user_service.register(data)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message)


@router.get(
    "/",
    response_model=list[UserResponse],
    summary="List all users (admin only)",
)
async def list_users(
    user_service: UserServiceDep,
    current_user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[UserResponse]:
    """Return a paginated list of all registered users. Admin only."""
    _assert_admin(current_user)
    return await user_service.list_users(limit=limit, offset=offset)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get a user profile by ID",
)
async def get_user(
    user_id: UUID,
    user_service: UserServiceDep,
    current_user: CurrentUser,
) -> UserResponse:
    """Return a user's public profile. Authenticated users only."""
    try:
        return await user_service.get_by_id(user_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update a user profile",
)
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    user_service: UserServiceDep,
    current_user: CurrentUser,
) -> UserResponse:
    """
    Partially update a user profile.

    Users can update their own profile. Admins can update anyone.
    Role changes require admin privileges.
    """
    _assert_self_or_admin(current_user, user_id)

    # Non-admin users cannot change roles
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    if data.role is not None and not caller.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can change user roles.",
        )

    try:
        return await user_service.update(user_id, data)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.message
        )


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user account (admin only)",
)
async def delete_user(
    user_id: UUID,
    user_service: UserServiceDep,
    current_user: CurrentUser,
) -> None:
    """Permanently delete a user. Admin only."""
    _assert_admin(current_user)
    try:
        await user_service.delete(user_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)


@router.post(
    "/{user_id}/promote",
    response_model=UserResponse,
    summary="Promote a user to admin (admin only)",
)
async def promote_user(
    user_id: UUID,
    user_service: UserServiceDep,
    current_user: CurrentUser,
) -> UserResponse:
    """Grant admin privileges to a user. Admin only."""
    _assert_admin(current_user)
    try:
        return await user_service.promote_to_admin(user_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.message
        )


@router.post(
    "/{user_id}/deactivate",
    response_model=UserResponse,
    summary="Deactivate a user account",
)
async def deactivate_user(
    user_id: UUID,
    user_service: UserServiceDep,
    current_user: CurrentUser,
) -> UserResponse:
    """Deactivate an account. Users can deactivate themselves; admins can deactivate anyone."""
    _assert_self_or_admin(current_user, user_id)
    try:
        return await user_service.deactivate(user_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.message
        )


@router.post(
    "/{user_id}/activate",
    response_model=UserResponse,
    summary="Re-activate a deactivated account (admin only)",
)
async def activate_user(
    user_id: UUID,
    user_service: UserServiceDep,
    current_user: CurrentUser,
) -> UserResponse:
    """Re-activate a previously deactivated account. Admin only."""
    _assert_admin(current_user)
    try:
        return await user_service.activate(user_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.message
        )


# ---------------------------------------------------------------------------
# Self-service password change
# ---------------------------------------------------------------------------

from pydantic import BaseModel, Field


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


@router.post(
    "/me/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change own password",
)
async def change_password(
    data: ChangePasswordRequest,
    user_service: UserServiceDep,
    current_user: CurrentUser,
) -> None:
    """Change the authenticated user's password."""
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        await user_service.change_password(
            caller.id,
            current_password=data.current_password,
            new_password=data.new_password,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.message
        )