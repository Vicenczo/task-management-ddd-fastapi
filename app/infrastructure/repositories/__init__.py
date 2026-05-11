"""
Infrastructure Repository Implementations.

Concrete SQLAlchemy adapters for the domain repository ports defined in
app.domain.repository_interfaces.

Import from here for clean wiring in dependency injection:
    from app.infrastructure.repositories import (
        SqlAlchemyUserRepository,
        SqlAlchemyProjectRepository,
        SqlAlchemyTaskRepository,
    )
"""
from app.infrastructure.repositories.project_repository import SqlAlchemyProjectRepository
from app.infrastructure.repositories.task_repository import SqlAlchemyTaskRepository
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository

__all__ = [
    "SqlAlchemyUserRepository",
    "SqlAlchemyProjectRepository",
    "SqlAlchemyTaskRepository",
]