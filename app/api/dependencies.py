from typing import Annotated, Optional
from fastapi import Depends, HTTPException, status
from jose import jwt, JWTError
from pydantic import ValidationError

from app.core.config import settings
from app.infrastructure.database.session import get_db_session as DbSession
from app.infrastructure.repositories.repository_impl import (
    SqlAlchemyUserRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyTaskRepository,
)
from app.application.services.user_service import UserService
from app.application.services.project_service import ProjectService
from app.application.services.task_service import TaskService
from app.domain.models.user import User


# --- Service Dependencies ---

def get_user_service(session: DbSession) -> UserService:
    return UserService(SqlAlchemyUserRepository(session))


def get_project_service(session: DbSession) -> ProjectService:
    return ProjectService(SqlAlchemyProjectRepository(session))


def get_task_service(session: DbSession) -> TaskService:
    return TaskService(SqlAlchemyTaskRepository(session))


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]


# --- Auth Dependencies ---

async def get_current_user(
        session: DbSession,
        token: Annotated[str, Depends(settings.OAUTH2_SCHEME)]
) -> User:
    """
    Dekodira JWT token i vraća korisnika iz baze.
    """
    try:
        # Koristimo JWT_SECRET i JWT_ALGORITHM iz novog config.py
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token ne sadrži subject (user_id).",
            )
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nije moguće validirati kredencijale.",
        )

    repo = SqlAlchemyUserRepository(session)
    user = await repo.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Korisnik nije pronađen."
        )

    return user


async def get_current_user_optional(
        session: DbSession,
        token: Annotated[Optional[str], Depends(settings.OAUTH2_SCHEME)] = None
) -> Optional[User]:
    """
    Vraća korisnika ako je ulogovan, inače vraća None bez bacanja Error-a.
    """
    if not token:
        return None
    try:
        return await get_current_user(session, token)
    except HTTPException:
        return None


# --- Dependency Aliases ---

# Ovo je ono što je falilo u projects.py
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentUserOptional = Annotated[Optional[User], Depends(get_current_user_optional)]