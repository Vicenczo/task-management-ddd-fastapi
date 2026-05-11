"""
Mapper functions: ORM models <-> Domain entities.

This module is the Anti-Corruption Layer (ACL) boundary.
The ONLY place in the codebase allowed to import both ORM models
and domain entities simultaneously.

Naming convention:
  - `orm_to_*`   : ORM model  -> Domain entity  (used after DB reads)
  - `*_to_orm`   : Domain entity -> ORM model   (used before DB writes)
  - `update_*_orm`: Sync domain changes onto existing ORM instance (for UPDATE operations)

Design rules:
  - Pure functions: no side effects, no DB calls, no async.
  - Raise ValueError for corrupt/unexpected data from DB.
  - member_ids in Project are reconstructed from ProjectMemberModel rows
    passed in explicitly — keeps functions pure and testable.
"""
from app.domain.models.project import Project
from app.domain.models.task import Task
from app.domain.models.user import User
from app.domain.models.value_objects import ProjectStatus, TaskPriority, TaskStatus, UserRole
from app.infrastructure.database.models.project import ProjectMemberModel, ProjectModel
from app.infrastructure.database.models.task import TaskModel
from app.infrastructure.database.models.user import UserModel


# ---------------------------------------------------------------------------
# User mappers
# ---------------------------------------------------------------------------

def orm_to_user(orm: UserModel) -> User:
    """Convert a UserModel ORM row into a User domain entity."""
    return User(
        id=orm.id,
        email=orm.email,
        username=orm.username,
        full_name=orm.full_name,
        hashed_password=orm.hashed_password,
        role=UserRole(orm.role),
        is_active=orm.is_active,
        is_verified=orm.is_verified,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def user_to_orm(entity: User) -> UserModel:
    """Convert a User domain entity into a new UserModel ORM instance."""
    return UserModel(
        id=entity.id,
        email=entity.email,
        username=entity.username,
        full_name=entity.full_name,
        hashed_password=entity.hashed_password,
        role=str(entity.role),
        is_active=entity.is_active,
        is_verified=entity.is_verified,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def update_user_orm(orm: UserModel, entity: User) -> None:
    """
    Sync User domain entity changes onto an existing ORM instance.

    Preferred over creating a new ORM object for UPDATE — SQLAlchemy
    tracks dirty state on the existing session-bound instance.
    Does NOT update id or created_at (immutable fields).
    """
    orm.email = entity.email
    orm.username = entity.username
    orm.full_name = entity.full_name
    orm.hashed_password = entity.hashed_password
    orm.role = str(entity.role)
    orm.is_active = entity.is_active
    orm.is_verified = entity.is_verified
    orm.updated_at = entity.updated_at


# ---------------------------------------------------------------------------
# Project mappers
# ---------------------------------------------------------------------------

def orm_to_project(orm: ProjectModel, member_rows: list[ProjectMemberModel]) -> Project:
    """
    Convert a ProjectModel ORM row into a Project domain entity.

    Args:
        orm: The ProjectModel row (scalar fields only).
        member_rows: Explicit list of ProjectMemberModel rows for this project.
                     Passed in separately because the repository loads them
                     in the same query — keeping this function pure.
    """
    return Project(
        id=orm.id,
        name=orm.name,
        description=orm.description,
        slug=orm.slug,
        owner_id=orm.owner_id,
        member_ids={row.user_id for row in member_rows},
        status=ProjectStatus(orm.status),
        is_public=orm.is_public,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def project_to_orm(entity: Project) -> ProjectModel:
    """
    Convert a Project domain entity into a new ProjectModel ORM instance.

    Note: member_ids are NOT stored on ProjectModel itself.
    The repository syncs ProjectMemberModel rows separately.
    """
    return ProjectModel(
        id=entity.id,
        name=entity.name,
        description=entity.description,
        slug=entity.slug,
        owner_id=entity.owner_id,
        status=str(entity.status),
        is_public=entity.is_public,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def update_project_orm(orm: ProjectModel, entity: Project) -> None:
    """Sync Project scalar fields onto existing ORM instance. Does NOT touch members."""
    orm.name = entity.name
    orm.description = entity.description
    orm.slug = entity.slug
    orm.owner_id = entity.owner_id
    orm.status = str(entity.status)
    orm.is_public = entity.is_public
    orm.updated_at = entity.updated_at


def build_member_orm_rows(entity: Project) -> list[ProjectMemberModel]:
    """
    Build fresh ProjectMemberModel rows from a Project's member_ids set.

    Called during save/update to reconcile the member join table.
    Note: joined_at was removed in migration cacb644cae29 — not included.
    """
    return [
        ProjectMemberModel(project_id=entity.id, user_id=uid)
        for uid in entity.member_ids
    ]


# ---------------------------------------------------------------------------
# Task mappers
# ---------------------------------------------------------------------------

def orm_to_task(orm: TaskModel) -> Task:
    """Convert a TaskModel ORM row into a Task domain entity."""
    return Task(
        id=orm.id,
        title=orm.title,
        description=orm.description,
        project_id=orm.project_id,
        reporter_id=orm.reporter_id,
        assignee_id=orm.assignee_id,
        parent_task_id=orm.parent_task_id,
        status=TaskStatus(orm.status),
        priority=TaskPriority(orm.priority),
        due_date=orm.due_date,
        started_at=orm.started_at,
        completed_at=orm.completed_at,
        tags=list(orm.tags) if orm.tags else [],
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def task_to_orm(entity: Task) -> TaskModel:
    """Convert a Task domain entity into a new TaskModel ORM instance."""
    return TaskModel(
        id=entity.id,
        title=entity.title,
        description=entity.description,
        project_id=entity.project_id,
        reporter_id=entity.reporter_id,
        assignee_id=entity.assignee_id,
        parent_task_id=entity.parent_task_id,
        status=str(entity.status),
        priority=str(entity.priority),
        due_date=entity.due_date,
        started_at=entity.started_at,
        completed_at=entity.completed_at,
        tags=list(entity.tags),
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def update_task_orm(orm: TaskModel, entity: Task) -> None:
    """
    Sync Task domain entity changes onto existing ORM instance.
    project_id and reporter_id are immutable after creation — not updated here.
    """
    orm.title = entity.title
    orm.description = entity.description
    orm.assignee_id = entity.assignee_id
    orm.parent_task_id = entity.parent_task_id
    orm.status = str(entity.status)
    orm.priority = str(entity.priority)
    orm.due_date = entity.due_date
    orm.started_at = entity.started_at
    orm.completed_at = entity.completed_at
    orm.tags = list(entity.tags)
    orm.updated_at = entity.updated_at