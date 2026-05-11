"""
Task-related DTOs.

TaskCreate       — create a new task in a project.
TaskUpdate       — partial update of task fields.
TaskStatusUpdate — dedicated status transition endpoint.
TaskAssign       — assign/reassign a task to a user.
TaskResponse     — full task representation.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.value_objects import TaskPriority, TaskStatus


class TaskCreate(BaseModel):
    """Create a new task. project_id comes from the URL path, not the body."""

    title: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=10000)
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee_id: UUID | None = None
    parent_task_id: UUID | None = None
    due_date: datetime | None = None
    tags: list[str] = Field(default_factory=list, max_length=20)


class TaskUpdate(BaseModel):
    """Partial task update. None fields are ignored."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=10000)
    priority: TaskPriority | None = None
    due_date: datetime | None = None
    tags: list[str] | None = None


class TaskStatusUpdate(BaseModel):
    """Explicit status transition. Validated against domain transition rules."""

    status: TaskStatus


class TaskAssign(BaseModel):
    """Assign or reassign a task. Send null user_id to unassign."""

    user_id: UUID | None = None


class TaskResponse(BaseModel):
    """Full task response."""

    model_config = {"from_attributes": True}

    id: UUID
    title: str
    description: str
    project_id: UUID
    reporter_id: UUID
    assignee_id: UUID | None
    parent_task_id: UUID | None
    status: TaskStatus
    priority: TaskPriority
    due_date: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    tags: list[str]
    is_overdue: bool
    is_subtask: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, task: object) -> "TaskResponse":
        """Build response from a Task domain entity."""
        from app.domain.models.task import Task
        assert isinstance(task, Task)
        return cls(
            id=task.id,
            title=task.title,
            description=task.description,
            project_id=task.project_id,
            reporter_id=task.reporter_id,
            assignee_id=task.assignee_id,
            parent_task_id=task.parent_task_id,
            status=task.status,
            priority=task.priority,
            due_date=task.due_date,
            started_at=task.started_at,
            completed_at=task.completed_at,
            tags=task.tags,
            is_overdue=task.is_overdue,
            is_subtask=task.is_subtask,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )