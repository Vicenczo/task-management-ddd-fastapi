"""
AI-powered Task endpoints.

Endpoints that require Ollama/LLM — mounted separately from CRUD task endpoints
so they can be disabled or versioned independently.

GET  /tasks/search-semantic           — semantic task search via vector similarity
GET  /tasks/{task_id}/suggest-subtasks — generate 3 AI subtask suggestions

Route design:
  These are intentionally NOT nested under /projects/{project_id} because:
  - Semantic search spans ALL projects (cross-project search).
  - Subtask suggestions are task-level, not project-level operations.

Mounted in api_router.py under prefix "/tasks" → full paths:
  GET /api/v1/tasks/search-semantic?query=...
  GET /api/v1/tasks/{task_id}/suggest-subtasks

Error handling delegated to global AppError handler.
"""
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.dependencies import CurrentUser, DbSession, TaskServiceDep

router = APIRouter()


# ── Response Models ──────────────────────────────────────────────────────────

class SubtaskSuggestion(BaseModel):
    """Single AI-generated subtask suggestion."""
    title: str
    index: int  # 1-based position in the suggestion list


class SubtaskSuggestionsResponse(BaseModel):
    """Response containing AI-generated subtask suggestions."""
    task_id: UUID
    suggestions: list[SubtaskSuggestion]
    model: str = "llama3"


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get(
    "/search-semantic",
    summary="Semantic task search using vector cosine similarity",
    response_description="List of tasks ordered by semantic similarity to the query",
)
async def semantic_search(
    query: str = Query(
        ...,
        min_length=3,
        max_length=500,
        description="Natural language query — e.g. 'fix authentication bug'",
    ),
    current_user: CurrentUser = ...,
    service: TaskServiceDep = ...,
    session: DbSession = ...,
    limit: int = Query(default=10, ge=1, le=50, description="Max results to return"),
) -> list[dict]:
    """
    Find tasks semantically similar to a natural language query.

    How it works:
    1. Converts `query` to a 4096-dim vector via llama3 (Ollama).
    2. Searches `task_embeddings` using cosine distance (`<=>` operator).
    3. JOINs with `tasks` to build full task data.
    4. Returns tasks ordered by similarity (closest match first).

    Requirements:
    - Ollama must be running: `ollama serve`
    - llama3 model must be pulled: `ollama pull llama3`
    - Tasks must have embeddings (auto-generated on task creation).

    Raises (handled globally):
        ValidationError → 422 if Ollama unavailable or query too short.

    Example:
        GET /api/v1/tasks/search-semantic?query=fix+login+bug&limit=5
    """
    results = await service.semantic_search(
        query=query,
        limit=limit,
        caller_session=session,
    )
    # Return as dicts with key fields for clarity
    # (TaskResponse already has all fields — reuse it)
    return [r.model_dump() for r in results]


@router.get(
    "/{task_id}/suggest-subtasks",
    response_model=SubtaskSuggestionsResponse,
    summary="Generate AI subtask suggestions for a task",
    response_description="3 AI-generated subtask title suggestions",
)
async def suggest_subtasks(
    task_id: UUID,
    current_user: CurrentUser,
    service: TaskServiceDep,
) -> SubtaskSuggestionsResponse:
    """
    Generate 3 logical subtask suggestions for a task using llama3.

    The LLM analyzes the task's title and description and proposes
    concrete, actionable subtasks that would help complete it.

    Requirements:
    - Ollama must be running: `ollama serve`
    - llama3 model must be pulled: `ollama pull llama3`

    Raises (handled globally):
        NotFoundError → 404 if task does not exist.
        ValidationError → 422 if Ollama is unavailable.

    Example response:
        {
          "task_id": "uuid-here",
          "suggestions": [
            {"title": "Write unit tests for auth module", "index": 1},
            {"title": "Update API documentation", "index": 2},
            {"title": "Code review with team lead", "index": 3}
          ],
          "model": "llama3"
        }
    """
    _, suggestions = await service.get_task_with_suggestions(task_id)

    return SubtaskSuggestionsResponse(
        task_id=task_id,
        suggestions=[
            SubtaskSuggestion(title=title, index=i + 1)
            for i, title in enumerate(suggestions)
        ],
    )