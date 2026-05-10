"""
ORM model for the tasks table.

Maps to domain entity: app.domain.models.task.Task

Design decisions:
  - project_id FK with CASCADE DELETE — tasks are deleted when project is deleted.
  - reporter_id FK with RESTRICT — cannot delete user who created tasks.
  - assignee_id FK nullable (task can be unassigned).
  - parent_task_id FK nullable, self-referential (subtask support).
  - tags stored as TEXT array via PostgreSQL ARRAY type.
  - due_date, started_at, completed_at are nullable (optional lifecycle fields).
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.models.base import Base


class TaskModel(Base):
    """PostgreSQL table: tasks."""

    __tablename__ = "tasks"

    # --- Core fields ---
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # --- Foreign keys ---
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # --- Hierarchy (self-referential) ---
    parent_task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # --- Value objects (stored as strings) ---
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="backlog", index=True)
    priority: Mapped[str] = mapped_column(String(50), nullable=False, default="medium", index=True)

    # --- Timeline ---
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Tags (PostgreSQL native ARRAY) ---
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)),
        nullable=False,
        default=list,
        server_default="{}",
    )

    # --- Self-referential relationship (subtasks) ---
    subtasks: Mapped[list["TaskModel"]] = relationship(
        "TaskModel",
        back_populates="parent",
        cascade="all",
        lazy="select",
    )
    parent: Mapped["TaskModel | None"] = relationship(
        "TaskModel",
        back_populates="subtasks",
        remote_side="TaskModel.id",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"TaskModel(id={self.id!s:.8}..., "
            f"title='{self.title[:30]}', status='{self.status}')"
        )