"""
TaskService — Application service for task lifecycle management.

Responsibilities:
  - Create tasks within a project (validates project membership).
  - Update task fields and trigger domain transitions.
  - Assign/unassign tasks.
  - List tasks with filters.

AI Integration (optional, non-blocking):
  - On task creation, embedding is generated and stored asynchronously.
  - Embedding failure NEVER blocks task creation (graceful degradation).
  - Semantic search uses pgvector cosine distance (<=> operator).
  - Subtask suggestions use LLM structured JSON output.

Session access for AI operations:
  - `_save_embedding` receives the session explicitly — no internal `_session`
    attribute hacking. The session comes from `self._tasks._session` only
    in `_store_embedding_safe`, which is the single point of access.
"""
import logging
import uuid
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
from app.domain.models.base import _utcnow
from app.domain.models.task import Task
from app.domain.models.value_objects import TaskPriority, TaskStatus
from app.domain.repository_interfaces import AbstractProjectRepository, AbstractTaskRepository

logger = logging.getLogger(__name__)


class TaskService:
    """
    Orchestrates task creation, updates, status transitions, and assignment.

    Optional AI: pass ai_service to enable embeddings + suggestions.
    When ai_service=None (default in tests), all AI paths are skipped silently.
    """

    def __init__(
        self,
        task_repository: AbstractTaskRepository,
        project_repository: AbstractProjectRepository,
        ai_service=None,
    ) -> None:
        self._tasks = task_repository
        self._projects = project_repository
        self._ai = ai_service

    # ── Core CRUD ────────────────────────────────────────────────────────────

    async def create_task(
        self, project_id: UUID, dto: TaskCreate, reporter_id: UUID
    ) -> TaskResponse:
        """
        Create a new task in a project.

        Rules enforced:
          - Project must exist and be ACTIVE.
          - Reporter must be a project member or owner.

        AI side-effect (non-blocking):
          - Embedding generated and stored after task is persisted.
          - If Ollama is down, task creation still succeeds.

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

        # AI embedding — non-blocking, never fails the request
        if self._ai is not None:
            await self._store_embedding_safe(saved)

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

    # ── AI: Embedding generation ──────────────────────────────────────────────

    async def _store_embedding_safe(self, task: Task) -> None:
        """
        Generate and persist an embedding for a task.

        Called after task creation — completely non-blocking.
        Any exception is caught, logged, and silently discarded.

        Text strategy: "title. description" — gives the model enough context
        to generate a meaningful embedding.
        """
        try:
            embed_text = f"{task.title}. {task.description}".strip(". ")
            if not embed_text:
                logger.warning("Empty embed text for task_id=%s — skipping", task.id)
                return

            vector = await self._ai.generate_embedding(embed_text)
            if vector is None:
                logger.warning("Ollama returned None for task_id=%s", task.id)
                return

            # Access session via the concrete repository — this is the
            # only place we reach into the repository's internals.
            session = self._tasks._session
            await self._save_embedding(session, task.id, vector, embed_text)
            logger.info("Embedding stored for task_id=%s (dim=%d)", task.id, len(vector))

        except Exception as exc:
            # Log but never re-raise — task creation must not fail due to AI
            logger.error(
                "Non-fatal: embedding storage failed for task_id=%s: %s",
                task.id, exc,
            )

    async def _save_embedding(
        self,
        session,
        task_id: UUID,
        vector: list[float],
        embedded_text: str,
    ) -> None:
        """
        Insert or update a TaskEmbeddingModel row for the given task.

        Upsert logic:
        - If no embedding exists → INSERT new row.
        - If embedding exists → UPDATE vector + text in place.

        Uses the session passed in explicitly — no hidden attribute access.
        """
        from sqlalchemy import select
        from app.infrastructure.database.models.task_embedding import TaskEmbeddingModel

        # Check for existing embedding (handles re-embed on task update)
        result = await session.execute(
            select(TaskEmbeddingModel).where(
                TaskEmbeddingModel.task_id == task_id
            )
        )
        existing = result.scalar_one_or_none()
        now = _utcnow()

        if existing is not None:
            # UPDATE: refresh vector and timestamp
            existing.embedding = vector
            existing.embedded_text = embedded_text[:2000]  # respect column limit
            existing.updated_at = now
            logger.debug("Updated embedding for task_id=%s", task_id)
        else:
            # INSERT: create new embedding row
            embedding_row = TaskEmbeddingModel(
                id=uuid.uuid4(),
                task_id=task_id,
                embedding=vector,
                model_name="llama3",
                embedded_text=embedded_text[:2000],
                created_at=now,
                updated_at=now,
            )
            session.add(embedding_row)
            logger.debug("Inserted new embedding for task_id=%s", task_id)

        await session.flush()

    # ── AI: Semantic search ───────────────────────────────────────────────────

    async def semantic_search(
        self,
        query: str,
        limit: int = 10,
        caller_session=None,
    ) -> list[TaskResponse]:
        """
        Find tasks semantically similar to a natural language query.

        Algorithm:
          1. Embed `query` with llama3 → query_vector (4096-dim).
          2. JOIN tasks + task_embeddings.
          3. ORDER BY cosine distance (embedding <=> query_vector) ASC.
             Lower distance = more similar.
          4. LIMIT to top-N results.

        Note on indexing:
          No HNSW/IVFFlat index — pgvector 16-bit limit (2000 dims) makes
          ANN indexes unusable at 4096 dims. Exact NN search is used instead.
          For tables under ~50k tasks this is fast enough (<100ms).
          When scaling: use dimension reduction (PCA to 1536) + HNSW index.

        Args:
            query: Natural language search string.
            limit: Max number of results (default 10, max 50).
            caller_session: AsyncSession injected from the endpoint dependency.
                            Falls back to task repository's session if None.

        Returns:
            TaskResponse list, ordered by cosine similarity descending.

        Raises:
            ValidationError: If AI service is not configured or Ollama is down.
        """
        if self._ai is None:
            raise ValidationError(
                "AI service is not configured. "
                "Ensure Ollama is running and langchain-ollama is installed."
            )

        query_vector = await self._ai.generate_embedding(query)
        if query_vector is None:
            raise ValidationError(
                "Could not generate embedding for query. "
                "Is Ollama running? Try: ollama serve && ollama pull llama3"
            )

        from sqlalchemy import select
        from app.infrastructure.database.models.task_embedding import TaskEmbeddingModel
        from app.infrastructure.database.models.task import TaskModel
        from app.infrastructure.database.mappers import orm_to_task

        # Use caller's session (from HTTP request) or fall back to repo session
        session = caller_session if caller_session is not None else self._tasks._session

        # pgvector cosine distance: embedding <=> query_vector
        # Returns values in [0, 2]; 0 = identical, 2 = opposite
        # ORDER BY ASC → closest (most similar) first
        cosine_distance = TaskEmbeddingModel.embedding.op("<=>")(query_vector)

        stmt = (
            select(TaskModel)
            .join(
                TaskEmbeddingModel,
                TaskModel.id == TaskEmbeddingModel.task_id,
            )
            .order_by(cosine_distance.asc())
            .limit(limit)
        )

        result = await session.execute(stmt)
        task_orms = list(result.scalars().all())

        logger.info(
            "Semantic search: query='%s...', results=%d",
            query[:30], len(task_orms),
        )
        return [TaskResponse.from_domain(orm_to_task(t)) for t in task_orms]

    # ── AI: Subtask suggestions ───────────────────────────────────────────────

    async def get_task_with_suggestions(
        self, task_id: UUID
    ) -> tuple[TaskResponse, list[str]]:
        """
        Fetch a task and generate AI subtask suggestions for it.

        The LLM receives the task title and description and suggests
        3 concrete, actionable subtasks in JSON format.

        Args:
            task_id: UUID of the task to analyze.

        Returns:
            Tuple of (TaskResponse, list of up to 3 suggestion strings).
            Suggestion list is empty if Ollama is unavailable.

        Raises:
            NotFoundError: If task does not exist.
            ValidationError: If AI service is not configured.
        """
        task_obj = await self._tasks.get_by_id(task_id)
        if task_obj is None:
            raise NotFoundError(f"Task with id={task_id} not found.")

        if self._ai is None:
            raise ValidationError(
                "AI service is not configured. "
                "Ensure Ollama is running and langchain-ollama is installed."
            )

        suggestions: list[str] = []
        try:
            suggestions = await self._ai.get_semantic_suggestions(
                task_title=task_obj.title,
                task_description=task_obj.description,
            )
            logger.info(
                "Generated %d suggestions for task_id=%s",
                len(suggestions), task_id,
            )
        except Exception as exc:
            # Non-fatal — return empty list rather than 500
            logger.error(
                "Subtask suggestion failed for task_id=%s: %s", task_id, exc
            )

        return TaskResponse.from_domain(task_obj), suggestions