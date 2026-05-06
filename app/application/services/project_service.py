"""
Project Application Service.

Orchestrates use cases related to project management:
  - Creating and configuring projects
  - Status lifecycle transitions
  - Member management (add, remove, transfer ownership)
  - Access control (only members / owners can act on a project)

Dependency Inversion: depends on AbstractProjectRepository and
AbstractUserRepository interfaces, never on concrete implementations.
"""
from uuid import UUID

from app.application.dtos.project_schemas import (
    ProjectCreate,
    ProjectResponse,
    ProjectSummary,
    ProjectUpdate,
)
from app.application.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.domain.models.project import Project
from app.domain.models.value_objects import ProjectStatus
from app.domain.repository_interfaces import (
    AbstractProjectRepository,
    AbstractUserRepository,
)


class ProjectService:
    """
    Application service for Project use cases.

    `project_repo` handles all project persistence.
    `user_repo`    is used for existence checks when adding members.
    """

    def __init__(
        self,
        project_repo: AbstractProjectRepository,
        user_repo: AbstractUserRepository,
    ) -> None:
        self._projects = project_repo
        self._users = user_repo

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_or_raise(self, project_id: UUID) -> Project:
        project = await self._projects.get_by_id(project_id)
        if project is None:
            raise NotFoundError(f"Project '{project_id}' not found.")
        return project

    def _assert_owner(self, project: Project, caller_id: UUID) -> None:
        """Raise PermissionDeniedError if caller is not the project owner."""
        if project.owner_id != caller_id:
            raise PermissionDeniedError(
                "Only the project owner can perform this action."
            )

    def _assert_member(self, project: Project, caller_id: UUID) -> None:
        """Raise PermissionDeniedError if caller is not a project member/owner."""
        if not project.is_member(caller_id):
            raise PermissionDeniedError(
                "You must be a project member to perform this action."
            )

    async def _ensure_slug_available(self, slug: str) -> None:
        if await self._projects.exists_by_slug(slug):
            raise ConflictError(
                f"Slug '{slug}' is already taken. Choose a different project name or slug."
            )

    # ------------------------------------------------------------------
    # Use cases
    # ------------------------------------------------------------------

    async def create(self, data: ProjectCreate, owner_id: UUID) -> ProjectResponse:
        """
        Create a new project owned by `owner_id`.

        Steps:
          1. Verify slug uniqueness.
          2. Build the Project entity with validated data.
          3. Persist and return response.
        """
        slug = data.slug or ""
        if not slug:
            # Fallback: slugify the name inside the service
            import re
            slug = re.sub(r"[^\w\s\-]", "", data.name.lower().strip())
            slug = re.sub(r"[\s_]+", "-", slug).strip("-")

        await self._ensure_slug_available(slug)

        project = Project(
            name=data.name,
            description=data.description,
            slug=slug,
            owner_id=owner_id,
            is_public=data.is_public,
            status=ProjectStatus.PLANNING,
        )
        await self._projects.add(project)
        return ProjectResponse.from_domain(project)

    async def get_by_id(self, project_id: UUID, caller_id: UUID) -> ProjectResponse:
        """
        Return a project by ID.

        Private projects are only visible to members.
        """
        project = await self._get_or_raise(project_id)
        if not project.is_public:
            self._assert_member(project, caller_id)
        return ProjectResponse.from_domain(project)

    async def get_by_slug(self, slug: str, caller_id: UUID) -> ProjectResponse:
        """Return a project by its URL slug."""
        project = await self._projects.get_by_slug(slug)
        if project is None:
            raise NotFoundError(f"Project with slug '{slug}' not found.")
        if not project.is_public:
            self._assert_member(project, caller_id)
        return ProjectResponse.from_domain(project)

    async def list_my_projects(
        self,
        owner_id: UUID,
        *,
        status: ProjectStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ProjectSummary]:
        """Return all projects owned by the caller."""
        projects = await self._projects.list_by_owner(
            owner_id, status=status, limit=limit, offset=offset
        )
        return [ProjectSummary.from_domain(p) for p in projects]

    async def list_member_projects(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ProjectSummary]:
        """Return all projects where the user is a non-owner member."""
        projects = await self._projects.list_by_member(
            user_id, limit=limit, offset=offset
        )
        return [ProjectSummary.from_domain(p) for p in projects]

    async def list_public(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ProjectSummary]:
        """Return all public projects."""
        projects = await self._projects.list_public(limit=limit, offset=offset)
        return [ProjectSummary.from_domain(p) for p in projects]

    async def update(
        self,
        project_id: UUID,
        data: ProjectUpdate,
        caller_id: UUID,
    ) -> ProjectResponse:
        """Update project metadata. Only the owner can update."""
        project = await self._get_or_raise(project_id)
        self._assert_owner(project, caller_id)

        if data.name is not None:
            project.name = data.name
        if data.description is not None:
            project.description = data.description
        if data.is_public is not None:
            project.is_public = data.is_public

        project.touch()
        await self._projects.update(project)
        return ProjectResponse.from_domain(project)

    # ------------------------------------------------------------------
    # Status transitions (dedicated methods per transition)
    # ------------------------------------------------------------------

    async def activate(self, project_id: UUID, caller_id: UUID) -> ProjectResponse:
        """Transition project from PLANNING or ON_HOLD to ACTIVE."""
        project = await self._get_or_raise(project_id)
        self._assert_owner(project, caller_id)
        try:
            project.activate()
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        await self._projects.update(project)
        return ProjectResponse.from_domain(project)

    async def put_on_hold(self, project_id: UUID, caller_id: UUID) -> ProjectResponse:
        """Pause an active project."""
        project = await self._get_or_raise(project_id)
        self._assert_owner(project, caller_id)
        try:
            project.put_on_hold()
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        await self._projects.update(project)
        return ProjectResponse.from_domain(project)

    async def complete(self, project_id: UUID, caller_id: UUID) -> ProjectResponse:
        """Mark a project as completed."""
        project = await self._get_or_raise(project_id)
        self._assert_owner(project, caller_id)
        try:
            project.complete()
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        await self._projects.update(project)
        return ProjectResponse.from_domain(project)

    async def archive(self, project_id: UUID, caller_id: UUID) -> ProjectResponse:
        """Archive a project (terminal action)."""
        project = await self._get_or_raise(project_id)
        self._assert_owner(project, caller_id)
        try:
            project.archive()
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        await self._projects.update(project)
        return ProjectResponse.from_domain(project)

    # ------------------------------------------------------------------
    # Member management
    # ------------------------------------------------------------------

    async def add_member(
        self,
        project_id: UUID,
        new_member_id: UUID,
        caller_id: UUID,
    ) -> ProjectResponse:
        """
        Add a user to the project member list.

        Only the owner can add members.
        The target user must exist in the system.
        """
        project = await self._get_or_raise(project_id)
        self._assert_owner(project, caller_id)

        # Verify the target user exists
        target = await self._users.get_by_id(new_member_id)
        if target is None:
            raise NotFoundError(f"User '{new_member_id}' not found.")

        try:
            project.add_member(new_member_id)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        await self._projects.update(project)
        return ProjectResponse.from_domain(project)

    async def remove_member(
        self,
        project_id: UUID,
        member_id: UUID,
        caller_id: UUID,
    ) -> ProjectResponse:
        """Remove a member from the project. Only the owner can remove members."""
        project = await self._get_or_raise(project_id)
        self._assert_owner(project, caller_id)

        try:
            project.remove_member(member_id)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        await self._projects.update(project)
        return ProjectResponse.from_domain(project)

    async def transfer_ownership(
        self,
        project_id: UUID,
        new_owner_id: UUID,
        caller_id: UUID,
    ) -> ProjectResponse:
        """Transfer project ownership to another user."""
        project = await self._get_or_raise(project_id)
        self._assert_owner(project, caller_id)

        target = await self._users.get_by_id(new_owner_id)
        if target is None:
            raise NotFoundError(f"User '{new_owner_id}' not found.")

        try:
            project.transfer_ownership(new_owner_id)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        await self._projects.update(project)
        return ProjectResponse.from_domain(project)

    async def delete(self, project_id: UUID, caller_id: UUID) -> None:
        """Permanently delete a project and all its tasks (cascade)."""
        project = await self._get_or_raise(project_id)
        self._assert_owner(project, caller_id)
        await self._projects.delete(project_id)