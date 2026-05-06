"""
Task management endpoints.

All task routes are nested under a project context:
    /projects/{project_id}/tasks/

POST   /projects/{project_id}/tasks/                  — Create task.
GET    /projects/{project_id}/tasks/                  — List tasks (filtered).
GET    /projects/{project_id}/tasks/{task_id}          — Get single task.
PATCH  /projects/{project_id}/tasks/{task_id}          — Update task fields.
DELETE /projects/{project_id}/tasks/{task_id}          — Delete task.

Status transitions:
POST /projects/{project_id}/tasks/{task_id}/todo
POST /projects/{project_id}/tasks/{task_id}/start
POST /projects/{project_id}/tasks/{task_id}/review
POST /projects/{project_id}/tasks/{task_id}/complete
POST /projects/{project_id}/tasks/{task_id}/cancel
POST /projects/{project_id}/tasks/{task_id}/reopen

Assignment:
PUT /projects/{project_id}/tasks/{task_id}/assign

Standalone (not nested under project — for "my tasks" dashboard):
GET /tasks/mine  — All tasks assigned to the current user.
"""
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import CurrentUser, TaskServiceDep
from app.application.dtos.task_schemas import (
    TaskAssign,
    TaskCreate,
    TaskResponse,
    TaskSummary,
    TaskUpdate,
)
from app.application.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.domain.models.value_objects import TaskPriority, TaskStatus

# Two routers: nested under projects, and standalone for user-centric views
router = APIRouter(tags=["Tasks"])
my_tasks_router = APIRouter(prefix="/tasks", tags=["Tasks"])


# ---------------------------------------------------------------------------
# Shared exception mapping
# ---------------------------------------------------------------------------


def _raise_http(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)
    if isinstance(exc, PermissionDeniedError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.message)
    if isinstance(exc, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.message
        )
    raise exc


# ---------------------------------------------------------------------------
# User-centric view (standalone, not nested)
# ---------------------------------------------------------------------------


@my_tasks_router.get(
    "/mine",
    response_model=list[TaskSummary],
    summary="List tasks assigned to the current user",
)
async def list_my_tasks(
    task_service: TaskServiceDep,
    current_user: CurrentUser,
    task_status: TaskStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[TaskSummary]:
    """Return all tasks assigned to the authenticated user across all projects."""
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    return await task_service.list_my_tasks(
        caller.id, status=task_status, limit=limit, offset=offset
    )


# ---------------------------------------------------------------------------
# Project-nested task routes
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/tasks/",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task inside a project",
)
async def create_task(
    project_id: UUID,
    data: TaskCreate,
    task_service: TaskServiceDep,
    current_user: CurrentUser,
) -> TaskResponse:
    """
    Create a new task.

    Business rules enforced by the service:
      - Project must be ACTIVE.
      - Reporter (caller) must be a project member.
      - Assignee (if given) must be a project member.
    """
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        return await task_service.create(project_id, data, reporter_id=caller.id)
    except Exception as exc:
        _raise_http(exc)


@router.get(
    "/projects/{project_id}/tasks/",
    response_model=list[TaskSummary],
    summary="List tasks in a project",
)
async def list_project_tasks(
    project_id: UUID,
    task_service: TaskServiceDep,
    current_user: CurrentUser,
    task_status: TaskStatus | None = Query(default=None, alias="status"),
    priority: TaskPriority | None = Query(default=None),
    assignee_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[TaskSummary]:
    """
    List tasks in a project with optional filters.

    Results are ordered by priority (CRITICAL first) then created date.
    """
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        return await task_service.list_by_project(
            project_id,
            caller.id,
            status=task_status,
            priority=priority,
            assignee_id=assignee_id,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        _raise_http(exc)


@router.get(
    "/projects/{project_id}/tasks/{task_id}",
    response_model=TaskResponse,
    summary="Get a task by ID",
)
async def get_task(
    project_id: UUID,
    task_id: UUID,
    task_service: TaskServiceDep,
    current_user: CurrentUser,
) -> TaskResponse:
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        return await task_service.get_by_id(task_id, caller_id=caller.id)
    except Exception as exc:
        _raise_http(exc)


@router.get(
    "/projects/{project_id}/tasks/{task_id}/subtasks",
    response_model=list[TaskSummary],
    summary="List subtasks of a task",
)
async def list_subtasks(
    project_id: UUID,
    task_id: UUID,
    task_service: TaskServiceDep,
    current_user: CurrentUser,
) -> list[TaskSummary]:
    try:
        return await task_service.list_subtasks(task_id)
    except Exception as exc:
        _raise_http(exc)


@router.patch(
    "/projects/{project_id}/tasks/{task_id}",
    response_model=TaskResponse,
    summary="Update task fields",
)
async def update_task(
    project_id: UUID,
    task_id: UUID,
    data: TaskUpdate,
    task_service: TaskServiceDep,
    current_user: CurrentUser,
) -> TaskResponse:
    """
    Partially update task fields (PATCH).

    Status changes use the dedicated action endpoints below.
    """
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        return await task_service.update(task_id, data, caller_id=caller.id)
    except Exception as exc:
        _raise_http(exc)


@router.delete(
    "/projects/{project_id}/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task permanently",
)
async def delete_task(
    project_id: UUID,
    task_id: UUID,
    task_service: TaskServiceDep,
    current_user: CurrentUser,
) -> None:
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        await task_service.delete(task_id, caller_id=caller.id)
    except Exception as exc:
        _raise_http(exc)


# ---------------------------------------------------------------------------
# Status transition endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/tasks/{task_id}/todo",
    response_model=TaskResponse,
    summary="Move task to TODO (enter sprint)",
)
async def move_to_todo(
    project_id: UUID,
    task_id: UUID,
    task_service: TaskServiceDep,
    current_user: CurrentUser,
) -> TaskResponse:
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        return await task_service.move_to_todo(task_id, caller_id=caller.id)
    except Exception as exc:
        _raise_http(exc)


@router.post(
    "/projects/{project_id}/tasks/{task_id}/start",
    response_model=TaskResponse,
    summary="Start active work on a task (→ IN_PROGRESS)",
)
async def start_task(
    project_id: UUID,
    task_id: UUID,
    task_service: TaskServiceDep,
    current_user: CurrentUser,
) -> TaskResponse:
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        return await task_service.start(task_id, caller_id=caller.id)
    except Exception as exc:
        _raise_http(exc)


@router.post(
    "/projects/{project_id}/tasks/{task_id}/review",
    response_model=TaskResponse,
    summary="Submit task for review (→ IN_REVIEW)",
)
async def submit_for_review(
    project_id: UUID,
    task_id: UUID,
    task_service: TaskServiceDep,
    current_user: CurrentUser,
) -> TaskResponse:
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        return await task_service.submit_for_review(task_id, caller_id=caller.id)
    except Exception as exc:
        _raise_http(exc)


@router.post(
    "/projects/{project_id}/tasks/{task_id}/complete",
    response_model=TaskResponse,
    summary="Mark task as done (→ DONE)",
)
async def complete_task(
    project_id: UUID,
    task_id: UUID,
    task_service: TaskServiceDep,
    current_user: CurrentUser,
) -> TaskResponse:
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        return await task_service.complete(task_id, caller_id=caller.id)
    except Exception as exc:
        _raise_http(exc)


@router.post(
    "/projects/{project_id}/tasks/{task_id}/cancel",
    response_model=TaskResponse,
    summary="Cancel a task",
)
async def cancel_task(
    project_id: UUID,
    task_id: UUID,
    task_service: TaskServiceDep,
    current_user: CurrentUser,
) -> TaskResponse:
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        return await task_service.cancel(task_id, caller_id=caller.id)
    except Exception as exc:
        _raise_http(exc)


@router.post(
    "/projects/{project_id}/tasks/{task_id}/reopen",
    response_model=TaskResponse,
    summary="Reopen a cancelled task (→ BACKLOG)",
)
async def reopen_task(
    project_id: UUID,
    task_id: UUID,
    task_service: TaskServiceDep,
    current_user: CurrentUser,
) -> TaskResponse:
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        return await task_service.reopen(task_id, caller_id=caller.id)
    except Exception as exc:
        _raise_http(exc)


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------


@router.put(
    "/projects/{project_id}/tasks/{task_id}/assign",
    response_model=TaskResponse,
    summary="Assign or unassign a task",
)
async def assign_task(
    project_id: UUID,
    task_id: UUID,
    data: TaskAssign,
    task_service: TaskServiceDep,
    current_user: CurrentUser,
) -> TaskResponse:
    """
    Assign a task to a user or unassign it.

    Send `{"assignee_id": "<uuid>"}` to assign.
    Send `{"assignee_id": null}` to unassign.
    """
    from app.domain.models.user import User
    caller: User = current_user  # type: ignore[assignment]
    try:
        return await task_service.assign(task_id, data, caller_id=caller.id)
    except Exception as exc:
        _raise_http(exc)