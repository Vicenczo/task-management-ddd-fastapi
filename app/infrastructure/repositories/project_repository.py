"""
SQLAlchemy implementation of AbstractProjectRepository.

Project is an Aggregate Root — saving/updating a project also reconciles
its member set (ProjectMemberModel rows). This is the most complex repository
because of the member diff logic.
"""
import logging
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.project import Project
from app.domain.models.value_objects import ProjectStatus
from app.domain.repository_interfaces import AbstractProjectRepository
from app.infrastructure.database.mappers import (
    build_member_orm_rows,
    orm_to_project,
    project_to_orm,
    update_project_orm,
)
from app.infrastructure.database.models.project import ProjectMemberModel, ProjectModel

logger = logging.getLogger(__name__)


class SqlAlchemyProjectRepository(AbstractProjectRepository):
    """Concrete project repository backed by PostgreSQL via async SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _load_members(self, project_id: UUID) -> list[ProjectMemberModel]:
        """
        Internal helper: load all member rows for a given project.
        Kept separate so get_by_id and update can reuse it.
        """
        result = await self._session.execute(
            select(ProjectMemberModel).where(
                ProjectMemberModel.project_id == project_id
            )
        )
        return list(result.scalars().all())

    async def get_by_id(self, project_id: UUID) -> Project | None:
        """Fetch project by primary key, including member set."""
        result = await self._session.execute(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        member_rows = await self._load_members(project_id)
        return orm_to_project(orm, member_rows)

    async def get_by_slug(self, slug: str) -> Project | None:
        """Fetch project by URL slug, including member set."""
        result = await self._session.execute(
            select(ProjectModel).where(ProjectModel.slug == slug)
        )
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        member_rows = await self._load_members(orm.id)
        return orm_to_project(orm, member_rows)

    async def save(self, project: Project) -> Project:
        """
        Persist a new project and its initial member set.

        Member rows are inserted after the project row to satisfy FK constraint.
        """
        orm = project_to_orm(project)
        self._session.add(orm)
        await self._session.flush()  # Ensure project.id exists in DB before FK insert

        member_orms = build_member_orm_rows(project)
        for member_orm in member_orms:
            self._session.add(member_orm)
        await self._session.flush()

        logger.debug(
            "Saved new project: id=%s, slug=%s, members=%d",
            project.id, project.slug, len(member_orms),
        )
        member_rows = await self._load_members(project.id)
        return orm_to_project(orm, member_rows)

    async def update(self, project: Project) -> Project:
        """
        Update project scalar fields and reconcile member set.

        Member reconciliation strategy: DELETE all existing rows,
        INSERT fresh rows from entity. Simple and correct for small member sets.
        For large sets, a diff approach (add/remove delta) would be more efficient.

        Raises:
            ValueError: If project with given id does not exist.
        """
        result = await self._session.execute(
            select(ProjectModel).where(ProjectModel.id == project.id)
        )
        orm = result.scalar_one_or_none()
        if orm is None:
            raise ValueError(f"Project with id={project.id} not found — cannot update.")

        # Update scalar fields on session-tracked instance
        update_project_orm(orm, project)

        # Reconcile member rows: delete all, re-insert from entity
        await self._session.execute(
            delete(ProjectMemberModel).where(
                ProjectMemberModel.project_id == project.id
            )
        )
        for member_orm in build_member_orm_rows(project):
            self._session.add(member_orm)

        await self._session.flush()
        logger.debug("Updated project: id=%s, slug=%s", project.id, project.slug)

        member_rows = await self._load_members(project.id)
        return orm_to_project(orm, member_rows)

    async def list_by_owner(
        self,
        owner_id: UUID,
        *,
        status: ProjectStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Project]:
        """List projects owned by a user, with optional status filter."""
        stmt = (
            select(ProjectModel)
            .where(ProjectModel.owner_id == owner_id)
            .order_by(ProjectModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status is not None:
            stmt = stmt.where(ProjectModel.status == str(status))

        result = await self._session.execute(stmt)
        orms = list(result.scalars().all())

        # Load members for each project — N+1 acceptable for typical list sizes.
        # Optimize with selectinload if profiling shows it as bottleneck.
        projects = []
        for orm in orms:
            member_rows = await self._load_members(orm.id)
            projects.append(orm_to_project(orm, member_rows))
        return projects

    async def list_public(self, *, limit: int = 100, offset: int = 0) -> list[Project]:
        """List all public projects, newest first."""
        result = await self._session.execute(
            select(ProjectModel)
            .where(ProjectModel.is_public.is_(True))
            .order_by(ProjectModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        orms = list(result.scalars().all())
        projects = []
        for orm in orms:
            member_rows = await self._load_members(orm.id)
            projects.append(orm_to_project(orm, member_rows))
        return projects