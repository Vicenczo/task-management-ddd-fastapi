"""
ORM model for the task_embeddings table.

Design decisions:
  - Separate table (not a column on tasks) for two reasons:
    1. Single Responsibility: embedding is AI infrastructure concern,
       not core task data. Task queries don't need to JOIN embeddings.
    2. Schema flexibility: embedding dimensions or models may change
       without touching the tasks table.
  - One-to-one relationship with tasks (task_id is UNIQUE FK).
  - CASCADE DELETE: embedding is deleted when task is deleted.
  - pgvector VECTOR type stores the 4096-dimensional llama3 embedding.
  - model_name column tracks which model generated the embedding
    (useful when switching models or reindexing).

Prerequisites:
  - pgvector extension must be enabled: CREATE EXTENSION IF NOT EXISTS vector;
  - This is handled in the Alembic migration.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models.base import Base

try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    # Fallback for environments without pgvector installed
    # The column will not be created correctly, but the app can still import
    from sqlalchemy import Text as Vector  # type: ignore[assignment]
    PGVECTOR_AVAILABLE = False


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskEmbeddingModel(Base):
    """
    PostgreSQL table: task_embeddings.

    Stores 4096-dimensional llama3 vectors for semantic search.
    One embedding per task — updated when task title/description changes.
    """

    __tablename__ = "task_embeddings"
    __table_args__ = (
        UniqueConstraint("task_id", name="uq_task_embeddings_task_id"),
    )

    # FK to tasks — CASCADE DELETE ensures cleanup
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The 4096-dim embedding vector (llama3 via Ollama)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(4096),
        nullable=False,
    )

    # Track which model generated this embedding
    # Useful for bulk reindexing when switching models
    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="llama3",
    )

    # Text that was embedded — stored for cache invalidation
    # If task title/description changes, we compare to decide whether to re-embed
    embedded_text: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
        default="",
    )

    def __repr__(self) -> str:
        return (
            f"TaskEmbeddingModel(task_id={self.task_id!s:.8}..., "
            f"model='{self.model_name}')"
        )