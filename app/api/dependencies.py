"""
FastAPI Dependency Injection — Repository and Service wiring.
Sve na jednom mestu: Baza, Repozitorijumi, Servisi i Auth.
"""
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt

from app.core.config import settings
from app.domain.models.user import User
from app.domain.repository_interfaces import (
    AbstractProjectRepository,
    AbstractTaskRepository,
    AbstractUserRepository,
)
from app.application.services.user_service import UserService
from app.application.services.project_service import ProjectService
from app.application.services.task_service import TaskService

from app.infrastructure.database.session import get_db_session
from app.infrastructure.repositories.project_repository import SqlAlchemyProjectRepository
from app.infrastructure.repositories.task_repository import SqlAlchemyTaskRepository
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository

# --- Auth Scheme ---
# Koristimo šemu koju si već definisao u config.py
oauth2_scheme = settings.OAUTH2_SCHEME

# --- Type aliases ---
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


# ---------------------------------------------------------------------------
# Repository dependencies
# ---------------------------------------------------------------------------

def get_user_repository(session: DbSession) -> AbstractUserRepository:
    return SqlAlchemyUserRepository(session)


def get_project_repository(session: DbSession) -> AbstractProjectRepository:
    return SqlAlchemyProjectRepository(session)


def get_task_repository(session: DbSession) -> AbstractTaskRepository:
    return SqlAlchemyTaskRepository(session)


UserRepo = Annotated[AbstractUserRepository, Depends(get_user_repository)]
ProjectRepo = Annotated[AbstractProjectRepository, Depends(get_project_repository)]
TaskRepo = Annotated[AbstractTaskRepository, Depends(get_task_repository)]


# ---------------------------------------------------------------------------
# Service dependencies
# ---------------------------------------------------------------------------

def get_user_service(repo: UserRepo) -> UserService:
    return UserService(repo)


def get_project_service(repo: ProjectRepo) -> ProjectService:
    return ProjectService(repo)


def get_task_service(
    task_repo: TaskRepo,
    project_repo: ProjectRepo,
) -> TaskService:
    return TaskService(task_repository=task_repo, project_repository=project_repo)

UserServiceDep = Annotated[UserService, Depends(get_user_service)]
ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]


# ---------------------------------------------------------------------------
# Authentication dependencies
# ---------------------------------------------------------------------------

async def get_current_user(
        token: Annotated[str, Depends(oauth2_scheme)],
        user_repo: UserRepo,
) -> User:
    """Obavezan login - baca 401 ako token nije validan."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await user_repo.get_by_id(UUID(user_id))
    if user is None:
        raise credentials_exception
    return user


async def get_current_user_optional(
        token: Annotated[str | None, Depends(oauth2_scheme)] = None,
        user_repo: UserRepo = None,
) -> User | None:
    """Opcioni login - vraća None ako tokena nema ili nije validan."""
    if not token or not user_repo:
        return None
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        return await user_repo.get_by_id(UUID(user_id))
    except (JWTError, ValueError, AttributeError):
        return None


# --- Annotated za rute ---
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentUserOptional = Annotated[User | None, Depends(get_current_user_optional)]