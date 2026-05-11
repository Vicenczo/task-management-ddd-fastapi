"""
SQLAlchemy implementation of AbstractUserRepository.

Uses SQLAlchemy 2.0 style: select() + scalars() + execute().
All methods return pure domain entities — zero ORM leakage to callers.
"""
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.user import User
from app.domain.repository_interfaces import AbstractUserRepository
from app.infrastructure.database.mappers import orm_to_user, update_user_orm, user_to_orm
from app.infrastructure.database.models.user import UserModel

logger = logging.getLogger(__name__)


class SqlAlchemyUserRepository(AbstractUserRepository):
    """
    Concrete user repository backed by PostgreSQL via async SQLAlchemy.

    The session is injected per-request from FastAPI's dependency system.
    Transaction management (commit/rollback) is handled by get_db_session,
    NOT by this class — single responsibility.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Fetch user by primary key. Returns None if not found."""
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        orm = result.scalar_one_or_none()
        return orm_to_user(orm) if orm else None

    async def get_by_email(self, email: str) -> User | None:
        """Fetch user by email address (case-sensitive). Returns None if not found."""
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        orm = result.scalar_one_or_none()
        return orm_to_user(orm) if orm else None

    async def get_by_username(self, username: str) -> User | None:
        """Fetch user by username. Returns None if not found."""
        result = await self._session.execute(
            select(UserModel).where(UserModel.username == username)
        )
        orm = result.scalar_one_or_none()
        return orm_to_user(orm) if orm else None

    async def save(self, user: User) -> User:
        """
        Persist a new user to the database.

        The session will auto-flush before the next query, populating
        server-side defaults. Returns the same domain entity (id unchanged).
        """
        orm = user_to_orm(user)
        self._session.add(orm)
        await self._session.flush()  # Get DB defaults without committing
        logger.debug("Saved new user: id=%s, username=%s", user.id, user.username)
        return orm_to_user(orm)

    async def update(self, user: User) -> User:
        """
        Update an existing user row.

        Loads the existing ORM instance (session-tracked) and applies
        domain entity changes via update_user_orm — avoids detached instance issues.

        Raises:
            ValueError: If user with given id does not exist in DB.
        """
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user.id)
        )
        orm = result.scalar_one_or_none()
        if orm is None:
            raise ValueError(f"User with id={user.id} not found — cannot update.")
        update_user_orm(orm, user)
        await self._session.flush()
        logger.debug("Updated user: id=%s", user.id)
        return orm_to_user(orm)

    async def list_all(self, *, limit: int = 100, offset: int = 0) -> list[User]:
        """Return a paginated list of all users, ordered by creation date."""
        result = await self._session.execute(
            select(UserModel)
            .order_by(UserModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [orm_to_user(row) for row in result.scalars().all()]