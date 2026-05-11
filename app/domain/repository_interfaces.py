"""
Domain Repository Interfaces (Ports).

These abstract base classes define the contract between the Application layer
and the Infrastructure layer. They live in the Domain layer because the domain
dictates WHAT it needs — not HOW it is stored.

DDD pattern: Repository Port (interface here) + Repository Adapter (impl in infrastructure/).

Rules:
  - Only domain entities and primitive types as parameters/return values.
  - No SQLAlchemy, no ORM, no HTTP — zero infrastructure knowledge here.
  - All methods are async — the domain doesn't care, but infrastructure needs it.
"""
from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.project import Project
from app.domain.models.task import Task
from app.domain.models.user import User
from app.domain.models.value_objects import ProjectStatus, TaskPriority, TaskStatus


class AbstractUserRepository(ABC):
    """Port for user persistence operations."""

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def get_by_username(self, username: str) -> User | None: ...

    @abstractmethod
    async def save(self, user: User) -> User:
        """Persist a new user. Raises ValueError if email/username already exists."""
        ...

    @abstractmethod
    async def update(self, user: User) -> User:
        """Update an existing user. Raises ValueError if user not found."""
        ...

    @abstractmethod
    async def list_all(self, *, limit: int = 100, offset: int = 0) -> list[User]: ...


class AbstractProjectRepository(ABC):
    """Port for project persistence operations."""

    @abstractmethod
    async def get_by_id(self, project_id: UUID) -> Project | None: ...

    @abstractmethod
    async def get_by_slug(self, slug: str) -> Project | None: ...

    @abstractmethod
    async def save(self, project: Project) -> Project:
        """Persist a new project including its member set."""
        ...

    @abstractmethod
    async def update(self, project: Project) -> Project:
        """
        Update project scalar fields AND reconcile member set.
        Raises ValueError if project not found.
        """
        ...

    @abstractmethod
    async def list_by_owner(
        self,
        owner_id: UUID,
        *,
        status: ProjectStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Project]: ...

    @abstractmethod
    async def list_public(self, *, limit: int = 100, offset: int = 0) -> list[Project]: ...


class AbstractTaskRepository(ABC):
    """Port for task persistence operations."""

    @abstractmethod
    async def get_by_id(self, task_id: UUID) -> Task | None: ...

    @abstractmethod
    async def save(self, task: Task) -> Task:
        """Persist a new task."""
        ...

    @abstractmethod
    async def update(self, task: Task) -> Task:
        """Update an existing task. Raises ValueError if task not found."""
        ...

    @abstractmethod
    async def list_by_project(
        self,
        project_id: UUID,
        *,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        assignee_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]: ...

    @abstractmethod
    async def list_by_assignee(
        self,
        assignee_id: UUID,
        *,
        status: TaskStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]: ...