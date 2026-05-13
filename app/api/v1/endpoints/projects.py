"""
Project endpoints.

POST   /projects/                           — create project
GET    /projects/                           — list my projects
GET    /projects/public                     — list public projects
GET    /projects/{project_id}               — get project by ID
PATCH  /projects/{project_id}               — update project
PATCH  /projects/{project_id}/status        — transition status
POST   /projects/{project_id}/members       — add member
DELETE /projects/{project_id}/members/{id}  — remove member

Route ordering: /public MUST precede /{project_id}.
Error handling delegated to global AppError handler.
"""
from uuid import UUID

from fastapi import APIRouter, status

from app.api.dependencies import CurrentUser, ProjectServiceDep
from app.application.dtos.project_dtos import (
    ProjectCreate,
    ProjectMemberAdd,
    ProjectResponse,
    ProjectStatusUpdate,
    ProjectUpdate,
)

router = APIRouter()


# ── Collection routes (before /{project_id}) ───────────────────────────────

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
    Create a project in PLANNING status. Activate it before adding tasks.

    Raises (handled globally):
        ConflictError → 409 if slug already exists.
    """
    return await service.create_project(dto, owner_id=current_user.id)


@router.get("/", response_model=list[ProjectResponse], summary="List my projects")
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
    """All public projects — no auth required."""
    return await service.list_public_projects(limit=limit, offset=offset)


# ── Single resource routes (after static routes) ───────────────────────────

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
    """
    Raises (handled globally):
        NotFoundError → 404
    """
    return await service.get_project(project_id)


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
    Raises (handled globally):
        NotFoundError → 404, AuthorizationError → 403
    """
    return await service.update_project(project_id, dto, caller_id=current_user.id)


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
    Valid transitions: PLANNING→ACTIVE, ACTIVE→ON_HOLD/COMPLETED/ARCHIVED, etc.

    Raises (handled globally):
        NotFoundError → 404, AuthorizationError → 403, ValidationError → 422
    """
    return await service.transition_status(project_id, dto, caller_id=current_user.id)


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
    Raises (handled globally):
        NotFoundError → 404, AuthorizationError → 403, ValidationError → 422
    """
    return await service.add_member(project_id, dto, caller_id=current_user.id)


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
    Raises (handled globally):
        NotFoundError → 404, AuthorizationError → 403, ValidationError → 422
    """
    return await service.remove_member(project_id, user_id, caller_id=current_user.id)