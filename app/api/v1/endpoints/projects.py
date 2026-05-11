"""
Project endpoints.

POST   /projects/                             — create project           [AUTH]
GET    /projects/                             — list my projects         [AUTH]
GET    /projects/public                       — list public projects     [PUBLIC]
GET    /projects/{project_id}                 — get project by ID       [AUTH]
PATCH  /projects/{project_id}                 — update project          [OWNER]
PATCH  /projects/{project_id}/status          — transition status       [OWNER]
POST   /projects/{project_id}/members         — add member              [OWNER]
DELETE /projects/{project_id}/members/{uid}   — remove member           [OWNER]

CRITICAL: /public route MUST be defined before /{project_id}.
"""
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CurrentUser, ProjectServiceDep
from app.application.dtos.project_dtos import (
    ProjectCreate,
    ProjectMemberAdd,
    ProjectResponse,
    ProjectStatusUpdate,
    ProjectUpdate,
)
from app.application.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)

router = APIRouter()


# ── Collection routes ───────────────────────────────────────────────────────
# MUST come before /{project_id}

@router.post(
    "/",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project",
)
async def create_project(
    dto: ProjectCreate,
    current_user: CurrentUser,
    service: ProjectServiceDep,
) -> ProjectResponse:
    """
    Create a new project owned by the authenticated user.

    The project starts in PLANNING status — activate it before adding tasks.
    Slug is auto-generated from the project name if not provided.
    """
    try:
        return await service.create_project(dto, owner_id=current_user.id)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get(
    "/",
    response_model=list[ProjectResponse],
    summary="List my projects",
)
async def list_my_projects(
    current_user: CurrentUser,
    service: ProjectServiceDep,
    limit: int = 100,
    offset: int = 0,
) -> list[ProjectResponse]:
    """Return all projects owned by the authenticated user."""
    return await service.list_my_projects(current_user.id, limit=limit, offset=offset)


@router.get(
    "/public",
    response_model=list[ProjectResponse],
    summary="List public projects",
)
async def list_public_projects(
    service: ProjectServiceDep,
    limit: int = 100,
    offset: int = 0,
) -> list[ProjectResponse]:
    """
    Return all public projects. No authentication required.

    NOTE: This route MUST be defined before /{project_id} —
    otherwise FastAPI would attempt to parse 'public' as a UUID.
    """
    return await service.list_public_projects(limit=limit, offset=offset)


# ── Single resource routes ──────────────────────────────────────────────────

@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get project by ID",
)
async def get_project(
    project_id: UUID,
    service: ProjectServiceDep,
    current_user: CurrentUser,
) -> ProjectResponse:
    """Fetch a project by its UUID."""
    try:
        return await service.get_project(project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update project details",
)
async def update_project(
    project_id: UUID,
    dto: ProjectUpdate,
    current_user: CurrentUser,
    service: ProjectServiceDep,
) -> ProjectResponse:
    """
    Update project name, description, or visibility.
    Only the project owner can update project details.
    """
    try:
        return await service.update_project(project_id, dto, caller_id=current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.patch(
    "/{project_id}/status",
    response_model=ProjectResponse,
    summary="Transition project status",
)
async def transition_project_status(
    project_id: UUID,
    dto: ProjectStatusUpdate,
    current_user: CurrentUser,
    service: ProjectServiceDep,
) -> ProjectResponse:
    """
    Transition the project to a new status.

    Valid transitions:
    - PLANNING  → ACTIVE, ARCHIVED
    - ACTIVE    → ON_HOLD, COMPLETED, ARCHIVED
    - ON_HOLD   → ACTIVE, ARCHIVED
    - COMPLETED → ARCHIVED
    - ARCHIVED  → (terminal, no transitions)

    Project must be ACTIVE to accept new tasks.
    """
    try:
        return await service.transition_status(project_id, dto, caller_id=current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )


@router.post(
    "/{project_id}/members",
    response_model=ProjectResponse,
    summary="Add a member to the project",
)
async def add_member(
    project_id: UUID,
    dto: ProjectMemberAdd,
    current_user: CurrentUser,
    service: ProjectServiceDep,
) -> ProjectResponse:
    """
    Add a user to the project by their UUID.

    Use GET /users/ to find user IDs.
    Only the project owner can add members.
    The owner is automatically a member and cannot be added separately.
    """
    try:
        return await service.add_member(project_id, dto, caller_id=current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )


@router.delete(
    "/{project_id}/members/{user_id}",
    response_model=ProjectResponse,
    summary="Remove a member from the project",
)
async def remove_member(
    project_id: UUID,
    user_id: UUID,
    current_user: CurrentUser,
    service: ProjectServiceDep,
) -> ProjectResponse:
    """
    Remove a user from the project member list.
    The owner cannot be removed — transfer ownership first.
    Only the project owner can remove members.
    """
    try:
        return await service.remove_member(project_id, user_id, caller_id=current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )