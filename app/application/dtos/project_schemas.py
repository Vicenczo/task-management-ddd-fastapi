"""
Project DTOs (Data Transfer Objects).

Three-schema pattern:
  - ProjectCreate   : data required to create a new project.
  - ProjectUpdate   : data for modifying an existing project (PATCH).
  - ProjectResponse : data returned to the client.
"""
import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.models.value_objects import ProjectStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(value: str) -> str:
    """
    Convert a string into a URL-safe slug.

    Example: "My Awesome Project!" -> "my-awesome-project"
    """
    value = value.lower().strip()
    value = re.sub(r"[^\w\s\-]", "", value)   # Remove special chars
    value = re.sub(r"[\s_]+", "-", value)      # Spaces/underscores -> hyphen
    value = re.sub(r"-{2,}", "-", value)        # Collapse consecutive hyphens
    return value.strip("-")


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    """Schema for creating a new project."""

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=220,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="URL-friendly identifier. Auto-generated from name if omitted.",
    )
    is_public: bool = False

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("slug")
    @classmethod
    def validate_slug_format(cls, value: str | None) -> str | None:
        """Lowercase any explicitly-provided slug."""
        return value.lower() if value else value

    @model_validator(mode="after")
    def generate_slug_from_name(self) -> "ProjectCreate":
        """Auto-generate slug from name when not explicitly provided."""
        if not self.slug:
            self.slug = _slugify(self.name)
        return self


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

class ProjectUpdate(BaseModel):
    """
    Schema for updating an existing project (PATCH semantics).

    Status transitions are handled by dedicated action endpoints
    (e.g., POST /projects/{id}/activate), not via this schema.
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    is_public: bool | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        return value.strip() if value else value


# ---------------------------------------------------------------------------
# Status Transition
# ---------------------------------------------------------------------------

class ProjectStatusUpdate(BaseModel):
    """Schema for explicit project status transitions."""

    status: ProjectStatus


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class ProjectResponse(BaseModel):
    """Schema for project data returned to the client."""

    model_config = {"from_attributes": True}

    id: UUID
    name: str
    description: str
    slug: str
    owner_id: UUID
    member_ids: list[UUID]
    status: ProjectStatus
    is_public: bool
    total_members: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, project: object) -> "ProjectResponse":
        """Build response from a Project domain entity."""
        from app.domain.models.project import Project
        p: Project = project  # type: ignore[assignment]
        return cls(
            id=p.id,
            name=p.name,
            description=p.description,
            slug=p.slug,
            owner_id=p.owner_id,
            member_ids=list(p.member_ids),
            status=p.status,
            is_public=p.is_public,
            total_members=p.total_members,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )


# ---------------------------------------------------------------------------
# Summary (for lists)
# ---------------------------------------------------------------------------

class ProjectSummary(BaseModel):
    """Lightweight project card for list views."""

    model_config = {"from_attributes": True}

    id: UUID
    name: str
    slug: str
    status: ProjectStatus
    is_public: bool
    total_members: int
    owner_id: UUID

    @classmethod
    def from_domain(cls, project: object) -> "ProjectSummary":
        from app.domain.models.project import Project
        p: Project = project  # type: ignore[assignment]
        return cls(
            id=p.id,
            name=p.name,
            slug=p.slug,
            status=p.status,
            is_public=p.is_public,
            total_members=p.total_members,
            owner_id=p.owner_id,
        )