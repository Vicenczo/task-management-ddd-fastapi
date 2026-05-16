"""
TaskService — Application service for task lifecycle management.

[... postojeći docstring ...]

AI Integration:
  - On task creation, an embedding is generated asynchronously via AIService.
  - Embedding failure NEVER blocks task creation — it logs and continues.
  - Subtask suggestions are returned alongside the created task response
    so the API caller can optionally display them.
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

    Optional AI integration: pass ai_service to enable embedding generation
    and semantic subtask suggestions on task creation.
    """

    def __init__(
        self,
        task_repository: AbstractTaskRepository,
        project_repository: AbstractProjectRepository,
        ai_service=None,  # Optional — injected in production, None in tests
    ) -> None:
        self._tasks = task_repository
        self._projects = project_repository
        self._ai = ai_service

    async def create_task(
        self, project_id: UUID, dto: TaskCreate, reporter_id: UUID
    ) -> TaskResponse:
        """
        Create a new task in a project.

        Rules:
          - Project must exist.
          - Reporter must be a project member or owner.
          - Project must be in ACTIVE status to accept tasks.

        AI side-effects (non-blocking):
          - Generates and stores embedding for semantic search.
          - Embedding failure is logged but does NOT fail the request.

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

        # ── AI: Generate and store embedding (non-blocking) ──────────────
        if self._ai is not None:
            await self._store_embedding_safe(saved)

        return TaskResponse.from_domain(saved)

    async def _store_embedding_safe(self, task: Task) -> None:
        """
        Generate embedding for a task and persist it to task_embeddings table.

        Failure is silently logged — never propagates to the caller.
        Text used for embedding: "<title>. <description>"
        """
        try:
            embed_text = f"{task.title}. {task.description}".strip()
            vector = await self._ai.generate_embedding(embed_text)

            if vector is None:
                logger.warning("Embedding returned None for task_id=%s", task.id)
                return

            await self._save_embedding(task.id, vector, embed_text)
            logger.info("Embedding stored for task_id=%s", task.id)

        except Exception as exc:
            logger.error(
                "Non-fatal: embedding storage failed for task_id=%s: %s",
                task.id, exc,
            )

    async def _save_embedding(
        self, task_id: UUID, vector: list[float], embedded_text: str
    ) -> None:
        """
        Persist or update the embedding in task_embeddings table.

        Uses raw SQLAlchemy to avoid circular imports with ORM models.
        Upsert pattern: INSERT ... ON CONFLICT DO UPDATE.
        """
        from sqlalchemy import text
        from app.infrastructure.database.models.task_embedding import TaskEmbeddingModel
        from app.domain.models.base import _utcnow
        import uuid

        # Check if embedding already exists (update case)
        from sqlalchemy import select
        # We need the session — retrieve it from the task repository
        session = self._tasks._session

        result = await session.execute(
            select(TaskEmbeddingModel).where(
                TaskEmbeddingModel.task_id == task_id
            )
        )
        existing = result.scalar_one_or_none()

        now = _utcnow()
        if existing is not None:
            existing.embedding = vector
            existing.embedded_text = embedded_text
            existing.updated_at = now
        else:
            embedding_row = TaskEmbeddingModel(
                id=uuid.uuid4(),
                task_id=task_id,
                embedding=vector,
                model_name="llama3",
                embedded_text=embedded_text,
                created_at=now,
                updated_at=now,
            )
            session.add(embedding_row)

        await session.flush()

    async def get_task_with_suggestions(
        self, task_id: UUID
    ) -> tuple[TaskResponse, list[str]]:
        """
        Fetch a task and generate AI subtask suggestions for it.

        Returns:
            (TaskResponse, list_of_subtask_title_strings)
            Subtask list is empty if AI service is unavailable.
        """
        task_obj = await self._tasks.get_by_id(task_id)
        if task_obj is None:
            raise NotFoundError(f"Task with id={task_id} not found.")

        suggestions: list[str] = []
        if self._ai is not None:
            try:
                suggestions = await self._ai.get_semantic_suggestions(
                    task_title=task_obj.title,
                    task_description=task_obj.description,
                )
            except Exception as exc:
                logger.error("Subtask suggestion failed for task_id=%s: %s", task_id, exc)

        return TaskResponse.from_domain(task_obj), suggestions

    # ── All other methods remain unchanged ───────────────────────────────

    async def get_task(self, task_id: UUID) -> TaskResponse:
        """Fetch a task by ID."""
        task = await self._tasks.get_by_id(task_id)
        if task is None:
            raise NotFoundError(f"Task with id={task_id} not found.")
        return TaskResponse.from_domain(task)

    async def update_task(
        self, task_id: UUID, dto: TaskUpdate, caller_id: UUID
    ) -> TaskResponse:
        task = await self._tasks.get_by_id(task_id)
        if task is None:
            raise NotFoundError(f"Task with id={task_id} not found.")
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
        tasks = await self._tasks.list_by_assignee(
            assignee_id, status=status, limit=limit, offset=offset
        )
        return [TaskResponse.from_domain(t) for t in tasks]

    async def semantic_search(
        self,
        query: str,
        limit: int = 10,
        caller_session=None,
    ) -> list[TaskResponse]:
        """
        Find tasks semantically similar to query using cosine similarity.

        Steps:
          1. Generate embedding for the query string.
          2. Search task_embeddings using pgvector cosine similarity operator (<=>).
          3. JOIN with tasks table to build TaskResponse objects.
          4. Return top-N results ordered by similarity.

        Args:
            query: Natural language search query.
            limit: Maximum number of results to return.
            caller_session: AsyncSession — passed from the endpoint dependency.

        Returns:
            List of TaskResponse sorted by semantic similarity (closest first).

        Raises:
            ValidationError: If AI service is unavailable.
        """
        if self._ai is None:
            raise ValidationError("AI service is not configured.")

        query_vector = await self._ai.generate_embedding(query)
        if query_vector is None:
            raise ValidationError(
                "Could not generate embedding for query. Is Ollama running?"
            )

        # pgvector cosine distance operator: <=>
        # Lower distance = more similar. We ORDER BY ASC to get closest first.
        from sqlalchemy import text
        from app.infrastructure.database.models.task_embedding import TaskEmbeddingModel
        from app.infrastructure.database.models.task import TaskModel
        from sqlalchemy import select

        session = caller_session or self._tasks._session

        # Build the semantic search query
        # We use <=> (cosine distance) which equals 1 - cosine_similarity
        stmt = (
            select(TaskModel)
            .join(
                TaskEmbeddingModel,
                TaskModel.id == TaskEmbeddingModel.task_id,
            )
            .order_by(
                TaskEmbeddingModel.embedding.op("<=>")(query_vector)
            )
            .limit(limit)
        )

        result = await session.execute(stmt)
        task_orms = result.scalars().all()

        from app.infrastructure.database.mappers import orm_to_task
        return [TaskResponse.from_domain(orm_to_task(t)) for t in task_orms]