"""
Task Application Service.

Orchestrates use cases related to task management:
  - Creating tasks inside projects (with project state validation)
  - Status lifecycle transitions
  - Assignment and priority changes
  - Due date management
  - Tag management
  - Subtask hierarchy

Cross-aggregate rule enforcement:
  - A task can only be created in an ACTIVE project.
  - The assignee must be a project member.
  - The parent task (if provided) must belong to the same project.
"""
from uuid import UUID

from app.application.dtos.task_schemas import (
    TaskAssign,
    TaskCreate,
    TaskResponse,
    TaskSummary,
    TaskUpdate,
)
from app.application.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.domain.models.task import Task
from app.domain.models.value_objects import TaskPriority, TaskStatus
from app.domain.repository_interfaces import (
    AbstractProjectRepository,
    AbstractTaskRepository,
    AbstractUserRepository,
)


class TaskService:
    """
    Application service for Task use cases.

    Receives three repositories — cross-aggregate checks require
    reading from project and user stores.
    """

    def __init__(
        self,
        task_repo: AbstractTaskRepository,
        project_repo: AbstractProjectRepository,
        user_repo: AbstractUserRepository,
    ) -> None:
        self._tasks = task_repo
        self._projects = project_repo
        self._users = user_repo

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_task_or_raise(self, task_id: UUID) -> Task:
        task = await self._tasks.get_by_id(task_id)
        if task is None:
            raise NotFoundError(f"Task '{task_id}' not found.")
        return task

    def _assert_project_member(self, project: object, caller_id: UUID) -> None:
        from app.domain.models.project import Project
        p: Project = project  # type: ignore[assignment]
        if not p.is_member(caller_id):
            raise PermissionDeniedError(
                "You must be a project member to manage its tasks."
            )

    # ------------------------------------------------------------------
    # Use cases
    # ------------------------------------------------------------------

    async def create(
        self,
        project_id: UUID,
        data: TaskCreate,
        reporter_id: UUID,
    ) -> TaskResponse:
        """
        Create a new task inside a project.

        Business rules enforced:
          - Project must be ACTIVE to accept new tasks.
          - Reporter must be a project member.
          - Assignee (if given) must be a project member.
          - Parent task (if given) must belong to the same project.
        """
        project = await self._projects.get_by_id(project_id)
        if project is None:
            raise NotFoundError(f"Project '{project_id}' not found.")

        if not project.can_accept_tasks():
            raise ValidationError(
                f"Project '{project.name}' is not active and cannot accept new tasks "
                f"(current status: '{project.status}')."
            )

        self._assert_project_member(project, reporter_id)

        if data.assignee_id is not None and not project.is_member(data.assignee_id):
            raise ValidationError(
                f"User '{data.assignee_id}' is not a member of this project "
                "and cannot be assigned to this task."
            )

        if data.parent_task_id is not None:
            parent = await self._tasks.get_by_id(data.parent_task_id)
            if parent is None:
                raise NotFoundError(f"Parent task '{data.parent_task_id}' not found.")
            if parent.project_id != project_id:
                raise ValidationError(
                    "Parent task must belong to the same project as the subtask."
                )

        task = Task(
            title=data.title,
            description=data.description,
            project_id=project_id,
            reporter_id=reporter_id,
            assignee_id=data.assignee_id,
            parent_task_id=data.parent_task_id,
            priority=data.priority,
            tags=list(data.tags),
        )

        if data.due_date is not None:
            try:
                task.set_due_date(data.due_date)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc

        await self._tasks.add(task)
        return TaskResponse.from_domain(task)

    async def get_by_id(self, task_id: UUID, caller_id: UUID) -> TaskResponse:
        """Return a task by ID. Caller must be a project member."""
        task = await self._get_task_or_raise(task_id)
        project = await self._projects.get_by_id(task.project_id)
        if project is not None:
            self._assert_project_member(project, caller_id)
        return TaskResponse.from_domain(task)

    async def list_by_project(
        self,
        project_id: UUID,
        caller_id: UUID,
        *,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        assignee_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TaskSummary]:
        """Return filtered tasks for a project. Caller must be a member."""
        project = await self._projects.get_by_id(project_id)
        if project is None:
            raise NotFoundError(f"Project '{project_id}' not found.")
        self._assert_project_member(project, caller_id)

        tasks = await self._tasks.list_by_project(
            project_id,
            status=status,
            priority=priority,
            assignee_id=assignee_id,
            limit=limit,
            offset=offset,
        )
        return [TaskSummary.from_domain(t) for t in tasks]

    async def list_my_tasks(
        self,
        user_id: UUID,
        *,
        status: TaskStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TaskSummary]:
        """Return all tasks assigned to the caller."""
        tasks = await self._tasks.list_assigned_to(
            user_id, status=status, limit=limit, offset=offset
        )
        return [TaskSummary.from_domain(t) for t in tasks]

    async def list_subtasks(self, parent_task_id: UUID) -> list[TaskSummary]:
        """Return direct children of a task."""
        await self._get_task_or_raise(parent_task_id)  # Verify parent exists
        tasks = await self._tasks.list_subtasks(parent_task_id)
        return [TaskSummary.from_domain(t) for t in tasks]

    async def update(
        self,
        task_id: UUID,
        data: TaskUpdate,
        caller_id: UUID,
    ) -> TaskResponse:
        """
        Apply a partial update to a task.

        Only project members can update tasks.
        Status transitions use dedicated methods.
        """
        task = await self._get_task_or_raise(task_id)
        project = await self._projects.get_by_id(task.project_id)
        if project is not None:
            self._assert_project_member(project, caller_id)

        if data.title is not None:
            task.title = data.title
        if data.description is not None:
            task.description = data.description

        if data.priority is not None:
            try:
                task.change_priority(data.priority)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc

        if data.clear_due_date:
            task.clear_due_date()
        elif data.due_date is not None:
            try:
                task.set_due_date(data.due_date)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc

        if data.tags is not None:
            # Replace full tag list: clear then add
            task.tags = data.tags

        task.touch()
        await self._tasks.update(task)
        return TaskResponse.from_domain(task)

    # ------------------------------------------------------------------
    # Status transition use cases
    # ------------------------------------------------------------------

    async def move_to_todo(self, task_id: UUID, caller_id: UUID) -> TaskResponse:
        """Move a task from BACKLOG to TODO (entering sprint)."""
        return await self._transition(task_id, caller_id, "move_to_todo")

    async def start(self, task_id: UUID, caller_id: UUID) -> TaskResponse:
        """Start active work — transitions task to IN_PROGRESS."""
        return await self._transition(task_id, caller_id, "start")

    async def submit_for_review(self, task_id: UUID, caller_id: UUID) -> TaskResponse:
        """Submit task for review — transitions to IN_REVIEW."""
        return await self._transition(task_id, caller_id, "submit_for_review")

    async def complete(self, task_id: UUID, caller_id: UUID) -> TaskResponse:
        """Mark task as done — transitions to DONE."""
        return await self._transition(task_id, caller_id, "complete")

    async def cancel(self, task_id: UUID, caller_id: UUID) -> TaskResponse:
        """Cancel a task."""
        return await self._transition(task_id, caller_id, "cancel")

    async def reopen(self, task_id: UUID, caller_id: UUID) -> TaskResponse:
        """Reopen a cancelled task — sends back to BACKLOG."""
        return await self._transition(task_id, caller_id, "reopen")

    async def _transition(
        self,
        task_id: UUID,
        caller_id: UUID,
        method_name: str,
    ) -> TaskResponse:
        """Generic state transition executor — reduces repetition."""
        task = await self._get_task_or_raise(task_id)
        project = await self._projects.get_by_id(task.project_id)
        if project is not None:
            self._assert_project_member(project, caller_id)

        method = getattr(task, method_name)
        try:
            method()
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        await self._tasks.update(task)
        return TaskResponse.from_domain(task)

    # ------------------------------------------------------------------
    # Assignment
    # ------------------------------------------------------------------

    async def assign(
        self,
        task_id: UUID,
        data: TaskAssign,
        caller_id: UUID,
    ) -> TaskResponse:
        """
        Assign or unassign a task.

        If `data.assignee_id` is None, the task is unassigned.
        Otherwise the assignee must be a project member.
        """
        task = await self._get_task_or_raise(task_id)
        project = await self._projects.get_by_id(task.project_id)
        if project is not None:
            self._assert_project_member(project, caller_id)

        if data.assignee_id is None:
            try:
                task.unassign()
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
        else:
            if project is not None and not project.is_member(data.assignee_id):
                raise ValidationError(
                    f"User '{data.assignee_id}' is not a member of this project."
                )
            try:
                task.assign_to(data.assignee_id)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc

        await self._tasks.update(task)
        return TaskResponse.from_domain(task)

    async def delete(self, task_id: UUID, caller_id: UUID) -> None:
        """Permanently delete a task."""
        task = await self._get_task_or_raise(task_id)
        project = await self._projects.get_by_id(task.project_id)
        if project is not None:
            self._assert_project_member(project, caller_id)
        await self._tasks.delete(task_id)

    async def count_by_project(
        self,
        project_id: UUID,
        *,
        status: TaskStatus | None = None,
    ) -> int:
        """Return task count for a project, optionally filtered by status."""
        return await self._tasks.count_by_project(project_id, status=status)