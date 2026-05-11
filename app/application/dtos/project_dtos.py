"""
Project-related DTOs.

ProjectCreate       — create a new project.
ProjectUpdate       — partial update of project fields.
ProjectStatusUpdate — dedicated endpoint for status transitions.
ProjectMemberAdd    — add a member by user_id.
ProjectResponse     — full project representation including member count.
"""
import re
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.domain.models.value_objects import ProjectStatus


def _slugify(value: str) -> str:
    """Convert a string to a URL-friendly slug."""
    value = value.lower().strip()
    value = re.sub(r"[^\w\s-]", "", value)
    value = re.sub(r"[\s_]+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-")


class ProjectCreate(BaseModel):
    """Create a new project. Slug is auto-generated from name if not provided."""

    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=5000)
    slug: str | None = Field(
        default=None,
        min_length=3,
        max_length=255,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="URL-friendly identifier. Auto-generated from name if omitted.",
    )
    is_public: bool = False

    @field_validator("slug", mode="before")
    @classmethod
    def normalize_slug(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _slugify(v)

    def resolve_slug(self) -> str:
        """Return provided slug or auto-generate from name."""
        return self.slug if self.slug else _slugify(self.name)


class ProjectUpdate(BaseModel):
    """Partial project update. None fields are ignored."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    is_public: bool | None = None


class ProjectStatusUpdate(BaseModel):
    """Explicit status transition request."""

    status: ProjectStatus


class ProjectMemberAdd(BaseModel):
    """Add a user to a project by their UUID."""

    user_id: UUID


class ProjectResponse(BaseModel):
    """Full project response including computed fields."""

    model_config = {"from_attributes": True}

    id: UUID
    name: str
    description: str
    slug: str
    owner_id: UUID
    status: ProjectStatus
    is_public: bool
    total_members: int
    member_ids: list[UUID]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, project: object) -> "ProjectResponse":
        """Build response from a Project domain entity."""
        from app.domain.models.project import Project
        assert isinstance(project, Project)
        return cls(
            id=project.id,
            name=project.name,
            description=project.description,
            slug=project.slug,
            owner_id=project.owner_id,
            status=project.status,
            is_public=project.is_public,
            total_members=project.total_members,
            member_ids=list(project.member_ids),
            created_at=project.created_at,
            updated_at=project.updated_at,
        )