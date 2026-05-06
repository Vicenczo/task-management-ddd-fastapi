"""
Domain Models — Javni API domenskog sloja.

Importovati entitete odavde, a ne direktno iz podmodula:
    from app.domain.models import User, Project, Task, TaskStatus
"""
from app.domain.models.base import Entity, _utcnow
from app.domain.models.project import Project
from app.domain.models.task import Task
from app.domain.models.user import User
from app.domain.models.value_objects import (
    ProjectStatus,
    TaskPriority,
    TaskStatus,
    UserRole,
)

__all__ = [
    # Base
    "Entity",
    "_utcnow",
    # Entities
    "User",
    "Project",
    "Task",
    # Value Objects
    "UserRole",
    "ProjectStatus",
    "TaskStatus",
    "TaskPriority",
]