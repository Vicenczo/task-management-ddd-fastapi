"""
SQLAlchemy implementation of AbstractTaskRepository.

Tasks are simpler than projects — no join table, no member reconciliation.
Filter methods support composable WHERE clauses via SQLAlchemy 2.0 style.
"""
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.task import Task
from app.domain.models.value_objects import TaskPriority, TaskStatus
from app.domain.repository_interfaces import AbstractTaskRepository
from app.infrastructure.database.mappers import orm_to_task, task_to_orm, update_task_orm
from app.infrastructure.database.models.task import TaskModel

logger = logging.getLogger(__name__)


class SqlAlchemyTaskRepository(AbstractTaskRepository):
    """Concrete task repository backed by PostgreSQL via async SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, task_id: UUID) -> Task | None:
        """Fetch task by primary key. Returns None if not found."""
        result = await self._session.execute(
            select(TaskModel).where(TaskModel.id == task_id)
        )
        orm = result.scalar_one_or_none()
        return orm_to_task(orm) if orm else None

    async def save(self, task: Task) -> Task:
        """Persist a new task. Returns the domain entity populated with DB defaults."""
        orm = task_to_orm(task)
        self._session.add(orm)
        await self._session.flush()
        logger.debug("Saved new task: id=%s, title=%s", task.id, task.title)
        return orm_to_task(orm)

    async def update(self, task: Task) -> Task:
        """
        Update an existing task row.

        Raises:
            ValueError: If task with given id does not exist.
        """
        result = await self._session.execute(
            select(TaskModel).where(TaskModel.id == task.id)
        )
        orm = result.scalar_one_or_none()
        if orm is None:
            raise ValueError(f"Task with id={task.id} not found — cannot update.")
        update_task_orm(orm, task)
        await self._session.flush()
        logger.debug("Updated task: id=%s", task.id)
        return orm_to_task(orm)

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
        """
        List tasks in a project with composable filters.
        Ordered by priority (ascending sort_order) then creation date.
        """
        stmt = (
            select(TaskModel)
            .where(TaskModel.project_id == project_id)
            .order_by(TaskModel.priority.asc(), TaskModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status is not None:
            stmt = stmt.where(TaskModel.status == str(status))
        if priority is not None:
            stmt = stmt.where(TaskModel.priority == str(priority))
        if assignee_id is not None:
            stmt = stmt.where(TaskModel.assignee_id == assignee_id)

        result = await self._session.execute(stmt)
        return [orm_to_task(row) for row in result.scalars().all()]

    async def list_by_assignee(
        self,
        assignee_id: UUID,
        *,
        status: TaskStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        """List tasks assigned to a specific user, with optional status filter."""
        stmt = (
            select(TaskModel)
            .where(TaskModel.assignee_id == assignee_id)
            .order_by(TaskModel.priority.asc(), TaskModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status is not None:
            stmt = stmt.where(TaskModel.status == str(status))

        result = await self._session.execute(stmt)
        return [orm_to_task(row) for row in result.scalars().all()]