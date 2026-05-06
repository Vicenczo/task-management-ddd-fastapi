"""
Project management endpoints.

POST   /projects/                          — Create a project.
GET    /projects/                          — List public projects.
GET    /projects/mine                      — List caller's own projects.
GET    /projects/member-of                 — List projects caller is a member of.
GET    /projects/{project_id}              — Get a single project.
GET    /projects/{slug}/by-slug            — Get a project by slug.
PATCH  /projects/{project_id}              — Update project metadata.
DELETE /projects/{project_id}              — Delete a project.

Status transitions (POST actions — not PATCH — to make intent explicit):
POST /projects/{project_id}/activate
POST /projects/{project_id}/hold
POST /projects/{project_id}/complete
POST /projects/{project_id}/archive

Member management:
POST   /projects/{project_id}/members/{user_id}   — Add member.
DELETE /projects/{project_id}/members/{user_id}   — Remove member.
POST   /projects/{project_id}/transfer/{user_id}  — Transfer ownership.
"""
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import CurrentUser, CurrentUserOptional, ProjectServiceDep
from app.application.dtos.project_schemas import (
    ProjectCreate,
    ProjectResponse,
    ProjectSummary,
    ProjectUpdate,
)
from app.application.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.domain.models.value_objects import ProjectStatus

router = APIRouter(prefix="/projects", tags=["Projects"])


# ---------------------------------------------------------------------------
# Shared exception → HTTP mapping helper
# ---------------------------------------------------------------------------


def _raise_http(exc: Exception) -> None:
    """Convert application exceptions to HTTP responses."""
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message)
    if isinstance(exc, PermissionDeniedError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.message)
    if isinstance(exc, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.message
        )
    raise exc  # Unexpected — let the global handler catch it


# ---------------------------------------------------------------------------
# Create / List
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project",
)
async def create_project(
    data: ProjectCreate,
    project_service: ProjectServiceDep,
    current_user: CurrentUser,
) -> ProjectResponse:
    """
    Create a project owned by the authenticated user.

    The slug is auto-generated from the name if not provided.
    """
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        return await project_service.create(data, owner_id=caller.id)
    except Exception as exc:
        _raise_http(exc)


@router.get(
    "/",
    response_model=list[ProjectSummary],
    summary="List all public projects",
)
async def list_public_projects(
    project_service: ProjectServiceDep,
    _current_user: CurrentUserOptional,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ProjectSummary]:
    """Return all non-archived public projects. Authentication optional."""
    return await project_service.list_public(limit=limit, offset=offset)


@router.get(
    "/mine",
    response_model=list[ProjectSummary],
    summary="List projects owned by the current user",
)
async def list_my_projects(
    project_service: ProjectServiceDep,
    current_user: CurrentUser,
    project_status: ProjectStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ProjectSummary]:
    """Return projects where the caller is the owner."""
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    return await project_service.list_my_projects(
        caller.id, status=project_status, limit=limit, offset=offset
    )


@router.get(
    "/member-of",
    response_model=list[ProjectSummary],
    summary="List projects where the current user is a member",
)
async def list_member_projects(
    project_service: ProjectServiceDep,
    current_user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ProjectSummary]:
    """Return projects where the caller is a non-owner member."""
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    return await project_service.list_member_projects(
        caller.id, limit=limit, offset=offset
    )


# ---------------------------------------------------------------------------
# Single project — by ID or slug
# ---------------------------------------------------------------------------


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get a project by ID",
)
async def get_project(
    project_id: UUID,
    project_service: ProjectServiceDep,
    current_user: CurrentUser,
) -> ProjectResponse:
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        return await project_service.get_by_id(project_id, caller_id=caller.id)
    except Exception as exc:
        _raise_http(exc)


@router.get(
    "/{slug}/by-slug",
    response_model=ProjectResponse,
    summary="Get a project by URL slug",
)
async def get_project_by_slug(
    slug: str,
    project_service: ProjectServiceDep,
    current_user: CurrentUser,
) -> ProjectResponse:
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        return await project_service.get_by_slug(slug, caller_id=caller.id)
    except Exception as exc:
        _raise_http(exc)


# ---------------------------------------------------------------------------
# Update / Delete
# ---------------------------------------------------------------------------


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update project metadata",
)
async def update_project(
    project_id: UUID,
    data: ProjectUpdate,
    project_service: ProjectServiceDep,
    current_user: CurrentUser,
) -> ProjectResponse:
    """Update name, description, or visibility. Owner only."""
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        return await project_service.update(project_id, data, caller_id=caller.id)
    except Exception as exc:
        _raise_http(exc)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a project permanently",
)
async def delete_project(
    project_id: UUID,
    project_service: ProjectServiceDep,
    current_user: CurrentUser,
) -> None:
    """Permanently delete a project and all its tasks. Owner only."""
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        await project_service.delete(project_id, caller_id=caller.id)
    except Exception as exc:
        _raise_http(exc)


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


@router.post(
    "/{project_id}/activate",
    response_model=ProjectResponse,
    summary="Activate a project (PLANNING or ON_HOLD → ACTIVE)",
)
async def activate_project(
    project_id: UUID,
    project_service: ProjectServiceDep,
    current_user: CurrentUser,
) -> ProjectResponse:
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        return await project_service.activate(project_id, caller_id=caller.id)
    except Exception as exc:
        _raise_http(exc)


@router.post(
    "/{project_id}/hold",
    response_model=ProjectResponse,
    summary="Put an active project on hold",
)
async def hold_project(
    project_id: UUID,
    project_service: ProjectServiceDep,
    current_user: CurrentUser,
) -> ProjectResponse:
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        return await project_service.put_on_hold(project_id, caller_id=caller.id)
    except Exception as exc:
        _raise_http(exc)


@router.post(
    "/{project_id}/complete",
    response_model=ProjectResponse,
    summary="Mark a project as completed",
)
async def complete_project(
    project_id: UUID,
    project_service: ProjectServiceDep,
    current_user: CurrentUser,
) -> ProjectResponse:
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        return await project_service.complete(project_id, caller_id=caller.id)
    except Exception as exc:
        _raise_http(exc)


@router.post(
    "/{project_id}/archive",
    response_model=ProjectResponse,
    summary="Archive a project (terminal action)",
)
async def archive_project(
    project_id: UUID,
    project_service: ProjectServiceDep,
    current_user: CurrentUser,
) -> ProjectResponse:
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        return await project_service.archive(project_id, caller_id=caller.id)
    except Exception as exc:
        _raise_http(exc)


# ---------------------------------------------------------------------------
# Member management
# ---------------------------------------------------------------------------


@router.post(
    "/{project_id}/members/{user_id}",
    response_model=ProjectResponse,
    summary="Add a member to the project",
)
async def add_member(
    project_id: UUID,
    user_id: UUID,
    project_service: ProjectServiceDep,
    current_user: CurrentUser,
) -> ProjectResponse:
    """Add a user as a project member. Owner only."""
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        return await project_service.add_member(project_id, user_id, caller_id=caller.id)
    except Exception as exc:
        _raise_http(exc)


@router.delete(
    "/{project_id}/members/{user_id}",
    response_model=ProjectResponse,
    summary="Remove a member from the project",
)
async def remove_member(
    project_id: UUID,
    user_id: UUID,
    project_service: ProjectServiceDep,
    current_user: CurrentUser,
) -> ProjectResponse:
    """Remove a project member. Owner only."""
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        return await project_service.remove_member(project_id, user_id, caller_id=caller.id)
    except Exception as exc:
        _raise_http(exc)


@router.post(
    "/{project_id}/transfer/{new_owner_id}",
    response_model=ProjectResponse,
    summary="Transfer project ownership",
)
async def transfer_ownership(
    project_id: UUID,
    new_owner_id: UUID,
    project_service: ProjectServiceDep,
    current_user: CurrentUser,
) -> ProjectResponse:
    """Transfer ownership to another project member. Current owner only."""
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        return await project_service.transfer_ownership(
            project_id, new_owner_id, caller_id=caller.id
        )
    except Exception as exc:
        _raise_http(exc)