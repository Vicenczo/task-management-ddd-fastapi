"""
Project endpoints.

POST   /projects/                          — create project
GET    /projects/                          — list my projects
GET    /projects/public                    — list public projects
GET    /projects/{id}                      — get project by ID
PATCH  /projects/{id}                      — update project
PATCH  /projects/{id}/status               — transition status
POST   /projects/{id}/members              — add member
DELETE /projects/{id}/members/{user_id}    — remove member
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


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    dto: ProjectCreate,
    current_user: CurrentUser,
    service: ProjectServiceDep,
) -> ProjectResponse:
    try:
        return await service.create_project(dto, owner_id=current_user.id)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get("/", response_model=list[ProjectResponse])
async def list_my_projects(
    current_user: CurrentUser,
    service: ProjectServiceDep,
    limit: int = 100,
    offset: int = 0,
) -> list[ProjectResponse]:
    return await service.list_my_projects(current_user.id, limit=limit, offset=offset)


@router.get("/public", response_model=list[ProjectResponse])
async def list_public_projects(
    service: ProjectServiceDep,
    limit: int = 100,
    offset: int = 0,
) -> list[ProjectResponse]:
    return await service.list_public_projects(limit=limit, offset=offset)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    service: ProjectServiceDep,
    current_user: CurrentUser,
) -> ProjectResponse:
    try:
        return await service.get_project(project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    dto: ProjectUpdate,
    current_user: CurrentUser,
    service: ProjectServiceDep,
) -> ProjectResponse:
    try:
        return await service.update_project(project_id, dto, caller_id=current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.patch("/{project_id}/status", response_model=ProjectResponse)
async def transition_project_status(
    project_id: UUID,
    dto: ProjectStatusUpdate,
    current_user: CurrentUser,
    service: ProjectServiceDep,
) -> ProjectResponse:
    try:
        return await service.transition_status(project_id, dto, caller_id=current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (AuthorizationError, ValidationError) as exc:
        code = status.HTTP_403_FORBIDDEN if isinstance(exc, AuthorizationError) else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=code, detail=str(exc))


@router.post("/{project_id}/members", response_model=ProjectResponse)
async def add_member(
    project_id: UUID,
    dto: ProjectMemberAdd,
    current_user: CurrentUser,
    service: ProjectServiceDep,
) -> ProjectResponse:
    try:
        return await service.add_member(project_id, dto, caller_id=current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (AuthorizationError, ValidationError) as exc:
        code = status.HTTP_403_FORBIDDEN if isinstance(exc, AuthorizationError) else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=code, detail=str(exc))


@router.delete("/{project_id}/members/{user_id}", response_model=ProjectResponse)
async def remove_member(
    project_id: UUID,
    user_id: UUID,
    current_user: CurrentUser,
    service: ProjectServiceDep,
) -> ProjectResponse:
    try:
        return await service.remove_member(project_id, user_id, caller_id=current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (AuthorizationError, ValidationError) as exc:
        code = status.HTTP_403_FORBIDDEN if isinstance(exc, AuthorizationError) else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=code, detail=str(exc))