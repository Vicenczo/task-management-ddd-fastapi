"""
ProjectService — Application service for project lifecycle management.

Responsibilities:
  - Create projects (validate slug uniqueness, set owner).
  - Update project fields and manage member set.
  - Orchestrate status transitions via domain methods.
  - Authorization checks (only owner/members can modify).

Domain logic lives in Project entity — service only orchestrates.
"""
import logging
from uuid import UUID

from app.application.dtos.project_dtos import (
    ProjectCreate,
    ProjectMemberAdd,
    ProjectResponse,
    ProjectStatusUpdate,
    ProjectUpdate,
)
from app.application.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.domain.models.project import Project
from app.domain.models.value_objects import ProjectStatus
from app.domain.repository_interfaces import AbstractProjectRepository

logger = logging.getLogger(__name__)


class ProjectService:
    """
    Orchestrates project creation, updates, member management, and status transitions.
    Receives AbstractProjectRepository — no SQLAlchemy knowledge.
    """

    def __init__(self, repository: AbstractProjectRepository) -> None:
        self._repo = repository

    async def create_project(
        self, dto: ProjectCreate, owner_id: UUID
    ) -> ProjectResponse:
        """
        Create a new project owned by the caller.

        Steps:
          1. Resolve slug (provided or auto-generated from name).
          2. Check slug uniqueness.
          3. Build domain entity (starts in PLANNING status).
          4. Persist and return response.

        Raises:
            ConflictError: If slug is already taken.
        """
        slug = dto.resolve_slug()
        if await self._repo.get_by_slug(slug):
            raise ConflictError(
                f"Slug '{slug}' is already in use. Choose a different project name or provide a custom slug."
            )

        project = Project(
            name=dto.name,
            description=dto.description,
            slug=slug,
            owner_id=owner_id,
            member_ids=set(),
            status=ProjectStatus.PLANNING,
            is_public=dto.is_public,
        )
        saved = await self._repo.save(project)
        logger.info("Project created: id=%s, slug=%s, owner=%s", saved.id, saved.slug, owner_id)
        return ProjectResponse.from_domain(saved)

    async def get_project(self, project_id: UUID) -> ProjectResponse:
        """
        Fetch a project by ID.

        Raises:
            NotFoundError: If project does not exist.
        """
        project = await self._repo.get_by_id(project_id)
        if project is None:
            raise NotFoundError(f"Project with id={project_id} not found.")
        return ProjectResponse.from_domain(project)

    async def get_by_slug(self, slug: str) -> ProjectResponse:
        """Fetch a project by slug."""
        project = await self._repo.get_by_slug(slug)
        if project is None:
            raise NotFoundError(f"Project with slug='{slug}' not found.")
        return ProjectResponse.from_domain(project)

    async def update_project(
        self, project_id: UUID, dto: ProjectUpdate, caller_id: UUID
    ) -> ProjectResponse:
        """
        Update project scalar fields (name, description, visibility).

        Raises:
            NotFoundError: If project does not exist.
            AuthorizationError: If caller is not the project owner.
        """
        project = await self._repo.get_by_id(project_id)
        if project is None:
            raise NotFoundError(f"Project with id={project_id} not found.")
        if project.owner_id != caller_id:
            raise AuthorizationError("Only the project owner can update project details.")

        if dto.name is not None:
            project.name = dto.name
            project.touch()
        if dto.description is not None:
            project.description = dto.description
            project.touch()
        if dto.is_public is not None:
            project.is_public = dto.is_public
            project.touch()

        updated = await self._repo.update(project)
        return ProjectResponse.from_domain(updated)

    async def transition_status(
        self, project_id: UUID, dto: ProjectStatusUpdate, caller_id: UUID
    ) -> ProjectResponse:
        """
        Transition project to a new status via domain rules.

        Raises:
            NotFoundError, AuthorizationError, ValidationError.
        """
        project = await self._repo.get_by_id(project_id)
        if project is None:
            raise NotFoundError(f"Project with id={project_id} not found.")
        if project.owner_id != caller_id:
            raise AuthorizationError("Only the project owner can change project status.")

        try:
            project.transition_to(dto.status)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        updated = await self._repo.update(project)
        return ProjectResponse.from_domain(updated)

    async def add_member(
        self, project_id: UUID, dto: ProjectMemberAdd, caller_id: UUID
    ) -> ProjectResponse:
        """
        Add a user to the project member set.

        Raises:
            NotFoundError, AuthorizationError, ValidationError.
        """
        project = await self._repo.get_by_id(project_id)
        if project is None:
            raise NotFoundError(f"Project with id={project_id} not found.")
        if project.owner_id != caller_id:
            raise AuthorizationError("Only the project owner can add members.")

        try:
            project.add_member(dto.user_id)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        updated = await self._repo.update(project)
        return ProjectResponse.from_domain(updated)

    async def remove_member(
        self, project_id: UUID, user_id: UUID, caller_id: UUID
    ) -> ProjectResponse:
        """Remove a user from the project member set."""
        project = await self._repo.get_by_id(project_id)
        if project is None:
            raise NotFoundError(f"Project with id={project_id} not found.")
        if project.owner_id != caller_id:
            raise AuthorizationError("Only the project owner can remove members.")

        try:
            project.remove_member(user_id)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        updated = await self._repo.update(project)
        return ProjectResponse.from_domain(updated)

    async def list_my_projects(
        self,
        owner_id: UUID,
        *,
        status: ProjectStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ProjectResponse]:
        """List projects owned by the caller."""
        projects = await self._repo.list_by_owner(
            owner_id, status=status, limit=limit, offset=offset
        )
        return [ProjectResponse.from_domain(p) for p in projects]

    async def list_public_projects(
        self, *, limit: int = 100, offset: int = 0
    ) -> list[ProjectResponse]:
        """List all public projects."""
        projects = await self._repo.list_public(limit=limit, offset=offset)
        return [ProjectResponse.from_domain(p) for p in projects]