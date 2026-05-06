"""
Mapper functions: ORM models <-> Domain entities.

This module is the Anti-Corruption Layer (ACL) boundary.
It is the only place in the infrastructure layer allowed to
import both ORM models and domain entities simultaneously.

Design rules:
  - `to_domain` functions: ORM -> Domain (used after DB reads).
  - `to_orm`    functions: Domain -> ORM (used before DB writes).
  - Mappers are pure functions — no side effects, no DB calls.
  - Raise `ValueError` for unexpected/corrupt data coming from DB.
"""
from app.domain.models.project import Project
from app.domain.models.task import Task
from app.domain.models.user import User
from app.infrastructure.database.models import ProjectMemberORM, ProjectORM, TaskORM, UserORM


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

def user_to_domain(orm: UserORM) -> User:
    """Convert a UserORM row into a User domain entity."""
    return User(
        id=orm.id,
        email=orm.email,
        username=orm.username,
        full_name=orm.full_name,
        hashed_password=orm.hashed_password,
        role=orm.role,
        is_active=orm.is_active,
        is_verified=orm.is_verified,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def user_to_orm(entity: User) -> UserORM:
    """Convert a User domain entity into a UserORM row."""
    return UserORM(
        id=entity.id,
        email=entity.email,
        username=entity.username,
        full_name=entity.full_name,
        hashed_password=entity.hashed_password,
        role=entity.role,
        is_active=entity.is_active,
        is_verified=entity.is_verified,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def update_user_orm(orm: UserORM, entity: User) -> None:
    """
    Sync a User domain entity's changes onto an existing ORM instance.

    Preferred over creating a new ORM object for updates — SQLAlchemy
    tracks changes on the existing instance already bound to the session.
    """
    orm.email = entity.email
    orm.username = entity.username
    orm.full_name = entity.full_name
    orm.hashed_password = entity.hashed_password
    orm.role = entity.role
    orm.is_active = entity.is_active
    orm.is_verified = entity.is_verified
    orm.updated_at = entity.updated_at


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

def project_to_domain(orm: ProjectORM, member_rows: list[ProjectMemberORM]) -> Project:
    """
    Convert a ProjectORM row into a Project domain entity.

    `member_rows` must be loaded separately (lazy="raise" is set on the
    relationship) and passed in explicitly to keep this function pure.
    """
    return Project(
        id=orm.id,
        name=orm.name,
        description=orm.description,
        slug=orm.slug,
        owner_id=orm.owner_id,
        member_ids={row.user_id for row in member_rows},
        status=orm.status,
        is_public=orm.is_public,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def project_to_orm(entity: Project) -> ProjectORM:
    """
    Convert a Project domain entity into a ProjectORM row.

    Note: `member_ids` are NOT stored on ProjectORM itself.
    The repository is responsible for syncing ProjectMemberORM rows.
    """
    return ProjectORM(
        id=entity.id,
        name=entity.name,
        description=entity.description,
        slug=entity.slug,
        owner_id=entity.owner_id,
        status=entity.status,
        is_public=entity.is_public,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def update_project_orm(orm: ProjectORM, entity: Project) -> None:
    """Sync a Project domain entity's scalar fields onto an existing ORM instance."""
    orm.name = entity.name
    orm.description = entity.description
    orm.slug = entity.slug
    orm.owner_id = entity.owner_id
    orm.status = entity.status
    orm.is_public = entity.is_public
    orm.updated_at = entity.updated_at


def build_member_orm_rows(entity: Project) -> list[ProjectMemberORM]:
    """
    Build a fresh list of ProjectMemberORM rows from a Project entity.

    Called during project updates to reconcile the member set.
    The repository diffs this list against existing rows.
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return [
        ProjectMemberORM(project_id=entity.id, user_id=uid, joined_at=now)
        for uid in entity.member_ids
    ]


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

def task_to_domain(orm: TaskORM) -> Task:
    """Convert a TaskORM row into a Task domain entity."""
    return Task(
        id=orm.id,
        title=orm.title,
        description=orm.description,
        project_id=orm.project_id,
        reporter_id=orm.reporter_id,
        assignee_id=orm.assignee_id,
        parent_task_id=orm.parent_task_id,
        status=orm.status,
        priority=orm.priority,
        due_date=orm.due_date,
        started_at=orm.started_at,
        completed_at=orm.completed_at,
        tags=list(orm.tags),  # ARRAY -> list copy (avoid mutating ORM state)
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def task_to_orm(entity: Task) -> TaskORM:
    """Convert a Task domain entity into a TaskORM row."""
    return TaskORM(
        id=entity.id,
        title=entity.title,
        description=entity.description,
        project_id=entity.project_id,
        reporter_id=entity.reporter_id,
        assignee_id=entity.assignee_id,
        parent_task_id=entity.parent_task_id,
        status=entity.status,
        priority=entity.priority,
        due_date=entity.due_date,
        started_at=entity.started_at,
        completed_at=entity.completed_at,
        tags=list(entity.tags),
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def update_task_orm(orm: TaskORM, entity: Task) -> None:
    """Sync a Task domain entity's changes onto an existing ORM instance."""
    orm.title = entity.title
    orm.description = entity.description
    orm.assignee_id = entity.assignee_id
    orm.parent_task_id = entity.parent_task_id
    orm.status = entity.status
    orm.priority = entity.priority
    orm.due_date = entity.due_date
    orm.started_at = entity.started_at
    orm.completed_at = entity.completed_at
    orm.tags = list(entity.tags)
    orm.updated_at = entity.updated_at