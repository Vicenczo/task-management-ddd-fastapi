"""
Application DTOs — public API for the schema layer.

Import from here, not from individual schema modules:
    from app.application.dtos import UserCreate, UserResponse, TaskCreate
"""
from app.application.dtos.project_schemas import (
    ProjectCreate,
    ProjectResponse,
    ProjectStatusUpdate,
    ProjectSummary,
    ProjectUpdate,
)
from app.application.dtos.task_schemas import (
    TaskAssign,
    TaskCreate,
    TaskResponse,
    TaskStatusUpdate,
    TaskSummary,
    TaskUpdate,
)
from app.application.dtos.user_schemas import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserSummary,
)

__all__ = [
    # User
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserSummary",
    # Project
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectStatusUpdate",
    "ProjectResponse",
    "ProjectSummary",
    # Task
    "TaskCreate",
    "TaskUpdate",
    "TaskStatusUpdate",
    "TaskAssign",
    "TaskResponse",
    "TaskSummary",
]