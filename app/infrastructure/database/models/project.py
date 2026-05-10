"""
ORM model for the projects table.

Maps to domain entity: app.domain.models.project.Project

Design decisions:
  - owner_id is a FK to users.id (NOT NULL — project must have an owner).
  - member_ids (set[UUID] in domain) is stored in a separate join table
    'project_members' — avoids ARRAY type and keeps the schema normalized.
  - slug has a unique index for URL routing (/projects/{slug}).
  - status stored as VARCHAR matching ProjectStatus StrEnum values.
"""
import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.models.base import Base


class ProjectMemberModel(Base):
    """
    Join table: project <-> user (many-to-many membership).

    Note: owner is NOT stored here — ownership lives on ProjectModel.owner_id.
    This table stores only non-owner members.
    """

    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class ProjectModel(Base):
    """PostgreSQL table: projects."""

    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_projects_slug"),
    )

    # --- Core fields ---
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # --- Ownership ---
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # --- Status & visibility ---
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="planning")
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # --- Relationships ---
    members: Mapped[list[ProjectMemberModel]] = relationship(
        "ProjectMemberModel",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"ProjectModel(id={self.id!s:.8}..., slug='{self.slug}', status='{self.status}')"