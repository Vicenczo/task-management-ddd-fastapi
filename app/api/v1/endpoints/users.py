"""
User endpoints.

GET    /users/me         — current user profile          [AUTH REQUIRED]
PATCH  /users/me         — update current user profile   [AUTH REQUIRED]
GET    /users/           — list all users                [AUTH REQUIRED]
GET    /users/{user_id}  — fetch user by UUID            [AUTH REQUIRED]

CRITICAL: /me and / routes MUST be defined before /{user_id}.
FastAPI matches routes in registration order — if /{user_id} comes first,
the string "me" is passed to UUID() which raises a 422 validation error.
"""
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CurrentUser, UserServiceDep
from app.application.dtos.user_dtos import UserResponse, UserUpdate
from app.application.exceptions import NotFoundError

router = APIRouter()


# ── /me routes ─────────────────────────────────────────────────────────────
# MUST come before /{user_id} to avoid "me" being parsed as a UUID

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def get_me(current_user: CurrentUser) -> UserResponse:
    """Returns the profile of the currently authenticated user."""
    return UserResponse.model_validate(current_user, from_attributes=True)


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update current user profile",
)
async def update_me(
    dto: UserUpdate,
    current_user: CurrentUser,
    service: UserServiceDep,
) -> UserResponse:
    """
    Update the authenticated user's profile.

    Only provided fields are changed — omit a field to leave it unchanged.
    Password is re-hashed automatically if provided.
    """
    try:
        return await service.update_profile(current_user.id, dto)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ── Collection route ────────────────────────────────────────────────────────
# MUST come before /{user_id}

@router.get(
    "/",
    response_model=list[UserResponse],
    summary="List all users",
)
async def list_users(
    service: UserServiceDep,
    current_user: CurrentUser,
    limit: int = 100,
    offset: int = 0,
) -> list[UserResponse]:
    """
    Return a paginated list of all registered users.
    Used primarily to look up user IDs when adding project members.
    """
    return await service.list_users(limit=limit, offset=offset)


# ── Single resource route ───────────────────────────────────────────────────
# MUST come last — path parameter {user_id} matches any string

@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
)
async def get_user(
    user_id: UUID,
    service: UserServiceDep,
    current_user: CurrentUser,
) -> UserResponse:
    """Fetch any registered user by their UUID. Requires authentication."""
    try:
        return await service.get_by_id(user_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))