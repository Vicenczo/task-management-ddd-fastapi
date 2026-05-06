"""
Concrete SQLAlchemy repository implementations.

These classes implement the abstract repository interfaces defined in
`app.domain.repository_interfaces` using async SQLAlchemy sessions.

Rules:
  - All methods are async.
  - No business logic — only query construction and mapper calls.
  - Domain entities are the return type of every public method.
  - ORM objects never escape this module.
"""
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.project import Project
from app.domain.models.task import Task
from app.domain.models.user import User
from app.domain.models.value_objects import ProjectStatus, TaskPriority, TaskStatus
from app.domain.repository_interfaces import (
    AbstractProjectRepository,
    AbstractTaskRepository,
    AbstractUserRepository,
)
from app.infrastructure.database.mappers import (
    build_member_orm_rows,
    project_to_domain,
    project_to_orm,
    task_to_domain,
    task_to_orm,
    update_project_orm,
    update_task_orm,
    update_user_orm,
    user_to_domain,
    user_to_orm,
)
from app.infrastructure.database.models import (
    ProjectMemberORM,
    ProjectORM,
    TaskORM,
    UserORM,
)


# ---------------------------------------------------------------------------
# SqlAlchemyUserRepository
# ---------------------------------------------------------------------------

class SqlAlchemyUserRepository(AbstractUserRepository):
    """PostgreSQL-backed User repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        row = await self._session.get(UserORM, user_id)
        return user_to_domain(row) if row else None

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(UserORM).where(UserORM.email == email.lower())
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return user_to_domain(row) if row else None

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(UserORM).where(UserORM.username == username)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return user_to_domain(row) if row else None

    async def list_all(self, *, limit: int = 50, offset: int = 0) -> list[User]:
        stmt = (
            select(UserORM)
            .order_by(UserORM.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [user_to_domain(r) for r in rows]

    async def add(self, user: User) -> None:
        orm = user_to_orm(user)
        self._session.add(orm)
        # Flush to catch constraint violations (duplicate email) within the transaction
        await self._session.flush()

    async def update(self, user: User) -> None:
        orm = await self._session.get(UserORM, user.id)
        if orm is None:
            raise ValueError(f"User {user.id} not found — cannot update.")
        update_user_orm(orm, user)
        await self._session.flush()

    async def delete(self, user_id: UUID) -> None:
        orm = await self._session.get(UserORM, user_id)
        if orm is None:
            raise ValueError(f"User {user_id} not found — cannot delete.")
        await self._session.delete(orm)
        await self._session.flush()

    async def exists_by_email(self, email: str) -> bool:
        stmt = select(func.count()).where(UserORM.email == email.lower())
        count: int = (await self._session.execute(stmt)).scalar_one()
        return count > 0

    async def exists_by_username(self, username: str) -> bool:
        stmt = select(func.count()).where(UserORM.username == username)
        count: int = (await self._session.execute(stmt)).scalar_one()
        return count > 0


# ---------------------------------------------------------------------------
# SqlAlchemyProjectRepository
# ---------------------------------------------------------------------------

class SqlAlchemyProjectRepository(AbstractProjectRepository):
    """PostgreSQL-backed Project repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Private helper: load member rows for a project ---

    async def _get_member_rows(self, project_id: UUID) -> list[ProjectMemberORM]:
        stmt = select(ProjectMemberORM).where(ProjectMemberORM.project_id == project_id)
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_by_id(self, project_id: UUID) -> Project | None:
        orm = await self._session.get(ProjectORM, project_id)
        if orm is None:
            return None
        member_rows = await self._get_member_rows(project_id)
        return project_to_domain(orm, member_rows)

    async def get_by_slug(self, slug: str) -> Project | None:
        stmt = select(ProjectORM).where(ProjectORM.slug == slug)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            return None
        member_rows = await self._get_member_rows(orm.id)
        return project_to_domain(orm, member_rows)

    async def list_by_owner(
        self,
        owner_id: UUID,
        *,
        status: ProjectStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Project]:
        stmt = select(ProjectORM).where(ProjectORM.owner_id == owner_id)
        if status is not None:
            stmt = stmt.where(ProjectORM.status == status)
        stmt = stmt.order_by(ProjectORM.updated_at.desc()).limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        result = []
        for orm in rows:
            member_rows = await self._get_member_rows(orm.id)
            result.append(project_to_domain(orm, member_rows))
        return result

    async def list_by_member(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Project]:
        stmt = (
            select(ProjectORM)
            .join(ProjectMemberORM, ProjectMemberORM.project_id == ProjectORM.id)
            .where(ProjectMemberORM.user_id == user_id)
            .order_by(ProjectORM.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        result = []
        for orm in rows:
            member_rows = await self._get_member_rows(orm.id)
            result.append(project_to_domain(orm, member_rows))
        return result

    async def list_public(self, *, limit: int = 50, offset: int = 0) -> list[Project]:
        stmt = (
            select(ProjectORM)
            .where(
                ProjectORM.is_public.is_(True),
                ProjectORM.status != ProjectStatus.ARCHIVED,
            )
            .order_by(ProjectORM.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        result = []
        for orm in rows:
            member_rows = await self._get_member_rows(orm.id)
            result.append(project_to_domain(orm, member_rows))
        return result

    async def add(self, project: Project) -> None:
        orm = project_to_orm(project)
        self._session.add(orm)
        # Flush to get the project's PK before inserting member rows
        await self._session.flush()
        for member_row in build_member_orm_rows(project):
            self._session.add(member_row)
        await self._session.flush()

    async def update(self, project: Project) -> None:
        orm = await self._session.get(ProjectORM, project.id)
        if orm is None:
            raise ValueError(f"Project {project.id} not found — cannot update.")
        update_project_orm(orm, project)

        # Reconcile member set: delete all existing rows, re-insert from entity
        # Simple and correct; for large member sets a diff approach is better
        await self._session.execute(
            delete(ProjectMemberORM).where(ProjectMemberORM.project_id == project.id)
        )
        for member_row in build_member_orm_rows(project):
            self._session.add(member_row)
        await self._session.flush()

    async def delete(self, project_id: UUID) -> None:
        orm = await self._session.get(ProjectORM, project_id)
        if orm is None:
            raise ValueError(f"Project {project_id} not found — cannot delete.")
        await self._session.delete(orm)
        await self._session.flush()

    async def exists_by_slug(self, slug: str) -> bool:
        stmt = select(func.count()).where(ProjectORM.slug == slug)
        count: int = (await self._session.execute(stmt)).scalar_one()
        return count > 0


# ---------------------------------------------------------------------------
# SqlAlchemyTaskRepository
# ---------------------------------------------------------------------------

class SqlAlchemyTaskRepository(AbstractTaskRepository):
    """PostgreSQL-backed Task repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, task_id: UUID) -> Task | None:
        row = await self._session.get(TaskORM, task_id)
        return task_to_domain(row) if row else None

    async def list_by_project(
        self,
        project_id: UUID,
        *,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        assignee_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        stmt = select(TaskORM).where(TaskORM.project_id == project_id)
        if status is not None:
            stmt = stmt.where(TaskORM.status == status)
        if priority is not None:
            stmt = stmt.where(TaskORM.priority == priority)
        if assignee_id is not None:
            stmt = stmt.where(TaskORM.assignee_id == assignee_id)
        # Order: CRITICAL first, then by creation date
        stmt = stmt.order_by(TaskORM.priority.asc(), TaskORM.created_at.asc())
        stmt = stmt.limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [task_to_domain(r) for r in rows]

    async def list_assigned_to(
        self,
        user_id: UUID,
        *,
        status: TaskStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        stmt = select(TaskORM).where(TaskORM.assignee_id == user_id)
        if status is not None:
            stmt = stmt.where(TaskORM.status == status)
        stmt = stmt.order_by(TaskORM.priority.asc(), TaskORM.created_at.asc())
        stmt = stmt.limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [task_to_domain(r) for r in rows]

    async def list_subtasks(self, parent_task_id: UUID) -> list[Task]:
        stmt = (
            select(TaskORM)
            .where(TaskORM.parent_task_id == parent_task_id)
            .order_by(TaskORM.created_at.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [task_to_domain(r) for r in rows]

    async def add(self, task: Task) -> None:
        orm = task_to_orm(task)
        self._session.add(orm)
        await self._session.flush()

    async def update(self, task: Task) -> None:
        orm = await self._session.get(TaskORM, task.id)
        if orm is None:
            raise ValueError(f"Task {task.id} not found — cannot update.")
        update_task_orm(orm, task)
        await self._session.flush()

    async def delete(self, task_id: UUID) -> None:
        orm = await self._session.get(TaskORM, task_id)
        if orm is None:
            raise ValueError(f"Task {task_id} not found — cannot delete.")
        await self._session.delete(orm)
        await self._session.flush()

    async def count_by_project(
        self,
        project_id: UUID,
        *,
        status: TaskStatus | None = None,
    ) -> int:
        stmt = select(func.count()).where(TaskORM.project_id == project_id)
        if status is not None:
            stmt = stmt.where(TaskORM.status == status)
        return (await self._session.execute(stmt)).scalar_one()