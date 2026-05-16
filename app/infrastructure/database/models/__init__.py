"""
Infrastructure ORM Models — Public API.

Import ORM models from here to ensure Alembic autogenerate
discovers all tables via the shared Base metadata.

Usage:
    from app.infrastructure.database.models import Base, UserModel, ProjectModel, TaskModel
"""
from app.infrastructure.database.models.base import Base
from app.infrastructure.database.models.project import ProjectMemberModel, ProjectModel
from app.infrastructure.database.models.task import TaskModel
from app.infrastructure.database.models.task_embedding import TaskEmbeddingModel
from app.infrastructure.database.models.user import UserModel

__all__ = [
    "Base",
    "UserModel",
    "ProjectModel",
    "ProjectMemberModel",
    "TaskModel",
    "TaskEmbeddingModel",
]