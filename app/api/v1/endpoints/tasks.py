"""
Task endpoints — nested under /projects/{project_id}/tasks/.

POST   /projects/{project_id}/tasks/                         — create task      [MEMBER]
GET    /projects/{project_id}/tasks/                         — list tasks       [MEMBER]
GET    /projects/{project_id}/tasks/{task_id}                — get task         [MEMBER]
PATCH  /projects/{project_id}/tasks/{task_id}                — update task      [MEMBER]
PATCH  /projects/{project_id}/tasks/{task_id}/status         — change status    [MEMBER]
PATCH  /projects/{project_id}/tasks/{task_id}/assign         — assign/unassign  [MEMBER]

Design note:
  Query param for status filter is named 'task_status' (not 'status') to avoid
  shadowing Python's built-in status and potential FastAPI conflicts.
"""
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

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
    summary="Create a new task in a project",
)
async def create_task(
    project_id: UUID,
    dto: TaskCreate,
    current_user: CurrentUser,
    service: TaskServiceDep,
) -> TaskResponse:
    """
    Create a new task in the specified project.

    Requirements:
    - Caller must be a project member or owner.
    - Project must be in ACTIVE status.
    - due_date must be in the future if provided.
    """
    try:
        return await service.create_task(project_id, dto, reporter_id=current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )


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
    """
    List tasks in a project with optional filters.

    Query params:
    - status: Filter by task status (backlog, todo, in_progress, in_review, done, cancelled)
    - priority: Filter by priority (critical, high, medium, low)
    - assignee_id: Filter by assigned user UUID
    - limit / offset: Pagination
    """
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
    """Fetch a single task by its UUID."""
    try:
        return await service.get_task(task_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


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
    Update task title, description, priority, due date, or tags.
    Only project members can update tasks.
    """
    try:
        return await service.update_task(task_id, dto, caller_id=current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )


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
    Move a task to a new status following Kanban flow rules.

    Valid transitions:
    - BACKLOG     → TODO, CANCELLED
    - TODO        → IN_PROGRESS, BACKLOG, CANCELLED
    - IN_PROGRESS → IN_REVIEW, TODO, CANCELLED
    - IN_REVIEW   → DONE, IN_PROGRESS, CANCELLED
    - DONE        → (terminal)
    - CANCELLED   → BACKLOG (reopen)
    """
    try:
        return await service.transition_status(task_id, dto, caller_id=current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )


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
    Assign a task to a user or unassign it.

    Send { "user_id": "<uuid>" } to assign.
    Send { "user_id": null } to unassign.
    Only project members can assign tasks.
    """
    try:
        return await service.assign_task(task_id, dto, caller_id=current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )