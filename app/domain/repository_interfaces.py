from uuid import UUID
from typing import Sequence, Optional
from abc import ABC, abstractmethod
from app.domain.models.user import User
from app.domain.models.project import Project
from app.domain.models.task import Task

class AbstractUserRepository(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> Optional[User]: ...
    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]: ...

class AbstractProjectRepository(ABC):
    @abstractmethod
    async def get_by_id(self, project_id: UUID) -> Optional[Project]: ...

class AbstractTaskRepository(ABC):
    @abstractmethod
    async def get_by_id(self, task_id: UUID) -> Optional[Task]: ...