"""
Application Data Transfer Objects (DTOs).

DTOs are the public contract of the Application layer.
They validate incoming data (Request DTOs) and shape outgoing data (Response DTOs).

Rules:
  - DTOs know nothing about SQLAlchemy or ORM models.
  - DTOs may reference domain value objects (StrEnum) for type safety.
  - Never return domain entities directly from routes — always map to a DTO.
"""
from app.application.dtos.project_dtos import (
    ProjectCreate,
    ProjectMemberAdd,
    ProjectResponse,
    ProjectStatusUpdate,
    ProjectUpdate,
)
from app.application.dtos.task_dtos import (
    TaskAssign,
    TaskCreate,
    TaskResponse,
    TaskStatusUpdate,
    TaskUpdate,
)
from app.application.dtos.user_dtos import (
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)

__all__ = [
    # User
    "UserCreate",
    "UserLogin",
    "UserUpdate",
    "UserResponse",
    "TokenResponse",
    # Project
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectStatusUpdate",
    "ProjectMemberAdd",
    "ProjectResponse",
    # Task
    "TaskCreate",
    "TaskUpdate",
    "TaskStatusUpdate",
    "TaskAssign",
    "TaskResponse",
]