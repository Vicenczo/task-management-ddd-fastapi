"""
SQLAlchemy ORM Models.

These classes represent database tables only.
They are intentionally separate from domain entities — this is the
Anti-Corruption Layer between the database schema and the domain model.

Rules enforced here:
  - No business logic (no methods that enforce domain rules).
  - No imports from app.domain (direction: infra -> domain is one-way,
    handled only in mappers, not in ORM models themselves).
  - Every FK column has an explicit index.
  - Timestamps are always stored as UTC.

Table naming convention: plural snake_case  (users, projects, tasks).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.models.value_objects import (
    ProjectStatus,
    TaskPriority,
    TaskStatus,
    UserRole,
)
from app.infrastructure.database.base import Base


# ---------------------------------------------------------------------------
# Shared column helpers
# ---------------------------------------------------------------------------

def _uuid_pk() -> Mapped[uuid.UUID]:
    """Primary key: native PostgreSQL UUID, server default via gen_random_uuid()."""
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=None,  # Python-side default is sufficient
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _created_at() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )


def _updated_at() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        onupdate=_utc_now,
    )


# ---------------------------------------------------------------------------
# UserORM
# ---------------------------------------------------------------------------

class UserORM(Base):
    """
    Persisted representation of the User domain entity.

    Stores credentials and role. Password is always stored hashed —
    the infrastructure security layer is responsible for hashing.
    """

    __tablename__ = "users"

    # --- Identity ---
    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False, default="")

    # --- Auth ---
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # --- Role & status ---
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum", create_type=True),
        nullable=False,
        default=UserRole.MEMBER,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # --- Audit ---
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    # --- Relationships (back-references only; FK lives on child side) ---
    owned_projects: Mapped[list["ProjectORM"]] = relationship(
        "ProjectORM",
        back_populates="owner",
        foreign_keys="ProjectORM.owner_id",
        lazy="raise",           # Explicit loading — no accidental N+1
        cascade="all, delete-orphan",
    )
    reported_tasks: Mapped[list["TaskORM"]] = relationship(
        "TaskORM",
        back_populates="reporter",
        foreign_keys="TaskORM.reporter_id",
        lazy="raise",
    )
    assigned_tasks: Mapped[list["TaskORM"]] = relationship(
        "TaskORM",
        back_populates="assignee",
        foreign_keys="TaskORM.assignee_id",
        lazy="raise",
    )

    # --- Constraints ---
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("username", name="uq_users_username"),
        # Partial index: fast lookup for active users by email (login path)
        Index("ix_users_email_active", "email", postgresql_where="is_active = true"),
        Index("ix_users_role", "role"),
    )


# ---------------------------------------------------------------------------
# ProjectMemberORM  (association table — many-to-many Users <-> Projects)
# ---------------------------------------------------------------------------

class ProjectMemberORM(Base):
    """
    Association table for project membership.

    Separating membership from ProjectORM keeps the main table lean
    and makes permission queries straightforward.
    """

    __tablename__ = "project_members"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )

    __table_args__ = (
        # Composite PK already acts as a unique constraint.
        # Extra index for "which projects does this user belong to?" queries.
        Index("ix_project_members_user_id", "user_id"),
    )


# ---------------------------------------------------------------------------
# ProjectORM
# ---------------------------------------------------------------------------

class ProjectORM(Base):
    """
    Persisted representation of the Project domain aggregate root.

    Members are stored in the `project_members` association table.
    The `owner_id` FK points to the single user who owns the project.
    """

    __tablename__ = "projects"

    # --- Identity ---
    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    slug: Mapped[str] = mapped_column(String(220), nullable=False)

    # --- Ownership (FK to users) ---
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # --- Status & visibility ---
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status_enum", create_type=True),
        nullable=False,
        default=ProjectStatus.PLANNING,
    )
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # --- Audit ---
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    # --- Relationships ---
    owner: Mapped["UserORM"] = relationship(
        "UserORM",
        back_populates="owned_projects",
        foreign_keys=[owner_id],
        lazy="raise",
    )
    members: Mapped[list["ProjectMemberORM"]] = relationship(
        "ProjectMemberORM",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    tasks: Mapped[list["TaskORM"]] = relationship(
        "TaskORM",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    # --- Constraints ---
    __table_args__ = (
        UniqueConstraint("slug", name="uq_projects_slug"),
        Index("ix_projects_owner_id", "owner_id"),
        Index("ix_projects_status", "status"),
        # Composite: owner's projects filtered by status (dashboard query)
        Index("ix_projects_owner_status", "owner_id", "status"),
    )


# ---------------------------------------------------------------------------
# TaskORM
# ---------------------------------------------------------------------------

class TaskORM(Base):
    """
    Persisted representation of the Task domain entity.

    Tags are stored as a native PostgreSQL ARRAY for efficient
    containment queries (@> operator). Parent-child hierarchy is
    self-referential via `parent_task_id`.
    """

    __tablename__ = "tasks"

    # --- Identity ---
    id: Mapped[uuid.UUID] = _uuid_pk()
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # --- Foreign Keys ---
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    parent_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),   # Subtask survives parent deletion
        nullable=True,
        default=None,
    )

    # --- Value Objects ---
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status_enum", create_type=True),
        nullable=False,
        default=TaskStatus.BACKLOG,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority, name="task_priority_enum", create_type=True),
        nullable=False,
        default=TaskPriority.MEDIUM,
    )

    # --- Timestamps ---
    due_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    # --- Tags (native PostgreSQL array) ---
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)),
        nullable=False,
        default=list,
        server_default="{}",
    )

    # --- Relationships ---
    project: Mapped["ProjectORM"] = relationship(
        "ProjectORM",
        back_populates="tasks",
        lazy="raise",
    )
    reporter: Mapped["UserORM"] = relationship(
        "UserORM",
        back_populates="reported_tasks",
        foreign_keys=[reporter_id],
        lazy="raise",
    )
    assignee: Mapped["UserORM | None"] = relationship(
        "UserORM",
        back_populates="assigned_tasks",
        foreign_keys=[assignee_id],
        lazy="raise",
    )
    subtasks: Mapped[list["TaskORM"]] = relationship(
        "TaskORM",
        foreign_keys=[parent_task_id],
        lazy="raise",
    )

    # --- Constraints & Indexes ---
    __table_args__ = (
        Index("ix_tasks_project_id", "project_id"),
        Index("ix_tasks_assignee_id", "assignee_id"),
        Index("ix_tasks_reporter_id", "reporter_id"),
        Index("ix_tasks_parent_task_id", "parent_task_id"),
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_priority", "priority"),
        # Composite: the most common dashboard/board query
        Index("ix_tasks_project_status", "project_id", "status"),
        # Composite: "my open tasks" query
        Index("ix_tasks_assignee_status", "assignee_id", "status"),
        # Partial index: overdue task monitoring (status not terminal, due_date set)
        Index(
            "ix_tasks_due_date_open",
            "due_date",
            postgresql_where="due_date IS NOT NULL AND status NOT IN ('done', 'cancelled')",
        ),
    )