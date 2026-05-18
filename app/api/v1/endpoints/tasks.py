"""
Task endpoints — nested under /projects/{project_id}/tasks/.

POST   /{project_id}/tasks/                      — create task
GET    /{project_id}/tasks/                      — list tasks
GET    /{project_id}/tasks/{task_id}             — get task
PATCH  /{project_id}/tasks/{task_id}             — update task
PATCH  /{project_id}/tasks/{task_id}/status      — transition status
PATCH  /{project_id}/tasks/{task_id}/assign      — assign/unassign

AI endpoints (semantic search, suggestions) are in ai_tasks.py.
Error handling delegated to global AppError handler.
"""
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.dependencies import CurrentUser, TaskServiceDep
from app.application.dtos.task_dtos import (
    TaskAssign,
    TaskCreate,
    TaskResponse,
    TaskStatusUpdate,
    TaskUpdate,
)
from app.domain.models.value_objects import TaskPriority, TaskStatus

router = APIRouter()


@router.post(
    "/{project_id}/tasks/",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task",
)
async def create_task(
    project_id: UUID,
    dto: TaskCreate,
    current_user: CurrentUser,
    service: TaskServiceDep,
) -> TaskResponse:
    """
    Project must be ACTIVE. Caller must be a member.
    On creation, an embedding is automatically generated (non-blocking).

    Raises (handled globally):
        NotFoundError → 404, AuthorizationError → 403, ValidationError → 422
    """
    return await service.create_task(project_id, dto, reporter_id=current_user.id)


@router.get(
    "/{project_id}/tasks/",
    response_model=list[TaskResponse],
    summary="List tasks in a project",
)
async def list_tasks(
    project_id: UUID,
    current_user: CurrentUser,
    service: TaskServiceDep,
    task_status: TaskStatus | None = Query(default=None, alias="status"),
    priority: TaskPriority | None = Query(default=None),
    assignee_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[TaskResponse]:
    """Filter by status, priority, or assignee. Paginated."""
    return await service.list_project_tasks(
        project_id,
        status=task_status,
        priority=priority,
        assignee_id=assignee_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{project_id}/tasks/{task_id}",
    response_model=TaskResponse,
    summary="Get a task by ID",
)
async def get_task(
    project_id: UUID,
    task_id: UUID,
    current_user: CurrentUser,
    service: TaskServiceDep,
) -> TaskResponse:
    """
    Raises (handled globally):
        NotFoundError → 404
    """
    return await service.get_task(task_id)


@router.patch(
    "/{project_id}/tasks/{task_id}",
    response_model=TaskResponse,
    summary="Update task fields",
)
async def update_task(
    project_id: UUID,
    task_id: UUID,
    dto: TaskUpdate,
    current_user: CurrentUser,
    service: TaskServiceDep,
) -> TaskResponse:
    """
    Raises (handled globally):
        NotFoundError → 404, AuthorizationError → 403, ValidationError → 422
    """
    return await service.update_task(task_id, dto, caller_id=current_user.id)


@router.patch(
    "/{project_id}/tasks/{task_id}/status",
    response_model=TaskResponse,
    summary="Transition task status",
)
async def transition_task_status(
    project_id: UUID,
    task_id: UUID,
    dto: TaskStatusUpdate,
    current_user: CurrentUser,
    service: TaskServiceDep,
) -> TaskResponse:
    """
    Kanban flow: BACKLOG→TODO→IN_PROGRESS→IN_REVIEW→DONE.

    Raises (handled globally):
        NotFoundError → 404, AuthorizationError → 403, ValidationError → 422
    """
    return await service.transition_status(task_id, dto, caller_id=current_user.id)


@router.patch(
    "/{project_id}/tasks/{task_id}/assign",
    response_model=TaskResponse,
    summary="Assign or unassign a task",
)
async def assign_task(
    project_id: UUID,
    task_id: UUID,
    dto: TaskAssign,
    current_user: CurrentUser,
    service: TaskServiceDep,
) -> TaskResponse:
    """
    { "user_id": "<uuid>" } to assign, { "user_id": null } to unassign.

    Raises (handled globally):
        NotFoundError → 404, AuthorizationError → 403, ValidationError → 422
    """
    return await service.assign_task(task_id, dto, caller_id=current_user.id)