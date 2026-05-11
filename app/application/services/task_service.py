"""
TaskService — Application service for task lifecycle management.

Responsibilities:
  - Create tasks within a project (validates project membership).
  - Update task fields and trigger domain transitions.
  - Assign/unassign tasks.
  - List tasks with filters.
"""
import logging
from uuid import UUID

from app.application.dtos.task_dtos import (
    TaskAssign,
    TaskCreate,
    TaskResponse,
    TaskStatusUpdate,
    TaskUpdate,
)
from app.application.exceptions import (
    AuthorizationError,
    NotFoundError,
    ValidationError,
)
from app.domain.models.task import Task
from app.domain.models.value_objects import TaskPriority, TaskStatus
from app.domain.repository_interfaces import AbstractProjectRepository, AbstractTaskRepository

logger = logging.getLogger(__name__)


class TaskService:
    """
    Orchestrates task creation, updates, status transitions, and assignment.

    Requires both task and project repositories — tasks are validated
    against their parent project's membership rules.
    """

    def __init__(
        self,
        task_repository: AbstractTaskRepository,
        project_repository: AbstractProjectRepository,
    ) -> None:
        self._tasks = task_repository
        self._projects = project_repository

    async def create_task(
        self, project_id: UUID, dto: TaskCreate, reporter_id: UUID
    ) -> TaskResponse:
        """
        Create a new task in a project.

        Rules:
          - Project must exist.
          - Reporter must be a project member or owner.
          - Project must be in ACTIVE status to accept tasks.

        Raises:
            NotFoundError, AuthorizationError, ValidationError.
        """
        project = await self._projects.get_by_id(project_id)
        if project is None:
            raise NotFoundError(f"Project with id={project_id} not found.")
        if not project.is_member(reporter_id):
            raise AuthorizationError("You must be a project member to create tasks.")
        if not project.can_accept_tasks():
            raise ValidationError(
                f"Project is in '{project.status}' status and cannot accept new tasks. "
                "Activate the project first."
            )

        task = Task(
            title=dto.title,
            description=dto.description,
            project_id=project_id,
            reporter_id=reporter_id,
            assignee_id=dto.assignee_id,
            parent_task_id=dto.parent_task_id,
            priority=dto.priority,
            tags=list(dto.tags),
        )

        if dto.due_date is not None:
            try:
                task.set_due_date(dto.due_date)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc

        saved = await self._tasks.save(task)
        logger.info("Task created: id=%s, project=%s", saved.id, project_id)
        return TaskResponse.from_domain(saved)

    async def get_task(self, task_id: UUID) -> TaskResponse:
        """Fetch a task by ID."""
        task = await self._tasks.get_by_id(task_id)
        if task is None:
            raise NotFoundError(f"Task with id={task_id} not found.")
        return TaskResponse.from_domain(task)

    async def update_task(
        self, task_id: UUID, dto: TaskUpdate, caller_id: UUID
    ) -> TaskResponse:
        """
        Update task fields (title, description, priority, due_date, tags).

        Raises:
            NotFoundError, AuthorizationError, ValidationError.
        """
        task = await self._tasks.get_by_id(task_id)
        if task is None:
            raise NotFoundError(f"Task with id={task_id} not found.")

        # Verify caller is member of the task's project
        project = await self._projects.get_by_id(task.project_id)
        if project is None or not project.is_member(caller_id):
            raise AuthorizationError("You must be a project member to update tasks.")

        if dto.title is not None:
            task.title = dto.title
            task.touch()
        if dto.description is not None:
            task.description = dto.description
            task.touch()
        if dto.priority is not None:
            try:
                task.change_priority(dto.priority)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
        if dto.due_date is not None:
            try:
                task.set_due_date(dto.due_date)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
        if dto.tags is not None:
            task.tags = dto.tags
            task.touch()

        updated = await self._tasks.update(task)
        return TaskResponse.from_domain(updated)

    async def transition_status(
        self, task_id: UUID, dto: TaskStatusUpdate, caller_id: UUID
    ) -> TaskResponse:
        """
        Trigger a domain status transition on the task.

        Raises:
            NotFoundError, AuthorizationError, ValidationError.
        """
        task = await self._tasks.get_by_id(task_id)
        if task is None:
            raise NotFoundError(f"Task with id={task_id} not found.")

        project = await self._projects.get_by_id(task.project_id)
        if project is None or not project.is_member(caller_id):
            raise AuthorizationError("You must be a project member to update task status.")

        try:
            task.transition_to(dto.status)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        updated = await self._tasks.update(task)
        return TaskResponse.from_domain(updated)

    async def assign_task(
        self, task_id: UUID, dto: TaskAssign, caller_id: UUID
    ) -> TaskResponse:
        """Assign or unassign a task."""
        task = await self._tasks.get_by_id(task_id)
        if task is None:
            raise NotFoundError(f"Task with id={task_id} not found.")

        project = await self._projects.get_by_id(task.project_id)
        if project is None or not project.is_member(caller_id):
            raise AuthorizationError("You must be a project member to assign tasks.")

        try:
            if dto.user_id is not None:
                task.assign_to(dto.user_id)
            else:
                task.unassign()
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        updated = await self._tasks.update(task)
        return TaskResponse.from_domain(updated)

    async def list_project_tasks(
        self,
        project_id: UUID,
        *,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        assignee_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TaskResponse]:
        """List tasks in a project with optional filters."""
        tasks = await self._tasks.list_by_project(
            project_id,
            status=status,
            priority=priority,
            assignee_id=assignee_id,
            limit=limit,
            offset=offset,
        )
        return [TaskResponse.from_domain(t) for t in tasks]

    async def list_my_tasks(
        self,
        assignee_id: UUID,
        *,
        status: TaskStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TaskResponse]:
        """List tasks assigned to the caller."""
        tasks = await self._tasks.list_by_assignee(
            assignee_id, status=status, limit=limit, offset=offset
        )
        return [TaskResponse.from_domain(t) for t in tasks]