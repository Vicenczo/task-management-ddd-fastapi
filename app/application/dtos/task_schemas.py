"""
Task DTOs (Data Transfer Objects).

Three-schema pattern:
  - TaskCreate        : data required to open a new task.
  - TaskUpdate        : data for modifying a task (PATCH).
  - TaskStatusUpdate  : dedicated schema for status transitions.
  - TaskAssign        : dedicated schema for assignment changes.
  - TaskResponse      : data returned to the client.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.models.value_objects import TaskPriority, TaskStatus


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

class TaskCreate(BaseModel):
    """Schema for creating a new task inside a project."""

    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=10_000)
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: datetime | None = None
    assignee_id: UUID | None = None
    parent_task_id: UUID | None = None
    tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        return value.strip()

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        """Lowercase, strip whitespace, remove duplicates, preserve order."""
        seen: set[str] = set()
        result: list[str] = []
        for tag in value:
            normalized = tag.strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
        return result

    @field_validator("due_date")
    @classmethod
    def due_date_must_be_aware(cls, value: datetime | None) -> datetime | None:
        """Reject naive datetimes to prevent timezone bugs."""
        if value is not None and value.tzinfo is None:
            raise ValueError("due_date must be a timezone-aware datetime (include UTC offset).")
        return value


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

class TaskUpdate(BaseModel):
    """
    Schema for updating task fields (PATCH semantics).

    Status transitions use a dedicated endpoint.
    All fields are optional — only provided fields are applied.
    """

    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=10_000)
    priority: TaskPriority | None = None
    due_date: datetime | None = None
    clear_due_date: bool = Field(
        default=False,
        description="Set to true to explicitly remove the due date.",
    )
    tags: list[str] | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        return value.strip() if value else value

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        seen: set[str] = set()
        result: list[str] = []
        for tag in value:
            normalized = tag.strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
        return result

    @model_validator(mode="after")
    def validate_due_date_conflict(self) -> "TaskUpdate":
        """Prevent setting a due_date and clearing it at the same time."""
        if self.due_date is not None and self.clear_due_date:
            raise ValueError("Cannot set 'due_date' and 'clear_due_date=true' simultaneously.")
        return self

    @field_validator("due_date")
    @classmethod
    def due_date_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("due_date must be a timezone-aware datetime (include UTC offset).")
        return value


# ---------------------------------------------------------------------------
# Dedicated action schemas
# ---------------------------------------------------------------------------

class TaskStatusUpdate(BaseModel):
    """Schema for explicit task status transitions."""

    status: TaskStatus


class TaskAssign(BaseModel):
    """Schema for assigning or unassigning a task."""

    assignee_id: UUID | None = Field(
        description="User ID to assign. Set to null to unassign."
    )


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class TaskResponse(BaseModel):
    """Full task representation returned to the client."""

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
    tags: list[str]
    due_date: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    is_overdue: bool
    is_assigned: bool
    is_subtask: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, task: object) -> "TaskResponse":
        """Build response from a Task domain entity."""
        from app.domain.models.task import Task
        t: Task = task  # type: ignore[assignment]
        return cls(
            id=t.id,
            title=t.title,
            description=t.description,
            project_id=t.project_id,
            reporter_id=t.reporter_id,
            assignee_id=t.assignee_id,
            parent_task_id=t.parent_task_id,
            status=t.status,
            priority=t.priority,
            tags=t.tags,
            due_date=t.due_date,
            started_at=t.started_at,
            completed_at=t.completed_at,
            is_overdue=t.is_overdue,
            is_assigned=t.is_assigned,
            is_subtask=t.is_subtask,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )


# ---------------------------------------------------------------------------
# Summary (for lists / kanban boards)
# ---------------------------------------------------------------------------

class TaskSummary(BaseModel):
    """Compact task card for board and list views."""

    model_config = {"from_attributes": True}

    id: UUID
    title: str
    status: TaskStatus
    priority: TaskPriority
    assignee_id: UUID | None
    due_date: datetime | None
    is_overdue: bool
    tags: list[str]

    @classmethod
    def from_domain(cls, task: object) -> "TaskSummary":
        from app.domain.models.task import Task
        t: Task = task  # type: ignore[assignment]
        return cls(
            id=t.id,
            title=t.title,
            status=t.status,
            priority=t.priority,
            assignee_id=t.assignee_id,
            due_date=t.due_date,
            is_overdue=t.is_overdue,
            tags=t.tags,
        )