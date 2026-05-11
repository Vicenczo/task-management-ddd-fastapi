"""
Task endpoints — nested under /projects/{project_id}/tasks/.

POST   /projects/{project_id}/tasks/                    — create task
GET    /projects/{project_id}/tasks/                    — list tasks in project
GET    /projects/{project_id}/tasks/{task_id}           — get task
PATCH  /projects/{project_id}/tasks/{task_id}           — update task
PATCH  /projects/{project_id}/tasks/{task_id}/status    — transition status
PATCH  /projects/{project_id}/tasks/{task_id}/assign    — assign/unassign
"""
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CurrentUser, TaskServiceDep
from app.application.dtos.task_dtos import (
    TaskAssign,
    TaskCreate,
    TaskResponse,
    TaskStatusUpdate,
    TaskUpdate,
)
from app.application.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.domain.models.value_objects import TaskPriority, TaskStatus

router = APIRouter()


@router.post(
    "/{project_id}/tasks/",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    project_id: UUID,
    dto: TaskCreate,
    current_user: CurrentUser,
    service: TaskServiceDep,
) -> TaskResponse:
    try:
        return await service.create_task(project_id, dto, reporter_id=current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (AuthorizationError, ValidationError) as exc:
        code = status.HTTP_403_FORBIDDEN if isinstance(exc, AuthorizationError) else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=code, detail=str(exc))


@router.get("/{project_id}/tasks/", response_model=list[TaskResponse])
async def list_tasks(
    project_id: UUID,
    current_user: CurrentUser,
    service: TaskServiceDep,
    task_status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    assignee_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[TaskResponse]:
    return await service.list_project_tasks(
        project_id,
        status=task_status,
        priority=priority,
        assignee_id=assignee_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{project_id}/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    project_id: UUID,
    task_id: UUID,
    current_user: CurrentUser,
    service: TaskServiceDep,
) -> TaskResponse:
    try:
        return await service.get_task(task_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/{project_id}/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    project_id: UUID,
    task_id: UUID,
    dto: TaskUpdate,
    current_user: CurrentUser,
    service: TaskServiceDep,
) -> TaskResponse:
    try:
        return await service.update_task(task_id, dto, caller_id=current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (AuthorizationError, ValidationError) as exc:
        code = status.HTTP_403_FORBIDDEN if isinstance(exc, AuthorizationError) else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=code, detail=str(exc))


@router.patch("/{project_id}/tasks/{task_id}/status", response_model=TaskResponse)
async def transition_task_status(
    project_id: UUID,
    task_id: UUID,
    dto: TaskStatusUpdate,
    current_user: CurrentUser,
    service: TaskServiceDep,
) -> TaskResponse:
    try:
        return await service.transition_status(task_id, dto, caller_id=current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (AuthorizationError, ValidationError) as exc:
        code = status.HTTP_403_FORBIDDEN if isinstance(exc, AuthorizationError) else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=code, detail=str(exc))


@router.patch("/{project_id}/tasks/{task_id}/assign", response_model=TaskResponse)
async def assign_task(
    project_id: UUID,
    task_id: UUID,
    dto: TaskAssign,
    current_user: CurrentUser,
    service: TaskServiceDep,
) -> TaskResponse:
    try:
        return await service.assign_task(task_id, dto, caller_id=current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (AuthorizationError, ValidationError) as exc:
        code = status.HTTP_403_FORBIDDEN if isinstance(exc, AuthorizationError) else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=code, detail=str(exc))