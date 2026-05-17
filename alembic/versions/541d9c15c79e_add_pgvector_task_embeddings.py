"""add_pgvector_task_embeddings

Revision ID: 541d9c15c79e
Revises: cacb644cae29
Create Date: 2026-05-16 01:52:40.489119

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '541d9c15c79e'
down_revision: Union[str, None] = 'cacb644cae29'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Step 2: Create task_embeddings table
    op.create_table(
        "task_embeddings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "task_id",
            sa.UUID(),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Placeholder type; actual vector type set via raw SQL below
        sa.Column(
            "embedding",
            sa.Text(),
            nullable=True,
        ),
        sa.Column("model_name", sa.String(length=100), nullable=False, server_default="llama3"),
        sa.Column("embedded_text", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", name="uq_task_embeddings_task_id"),
    )

    # Step 3: Change embedding column type to VECTOR(4096)
    # Using 4096 dimensions to fully support Llama 3 embeddings.
    # We use raw SQL to handle the vector type registration.
    op.execute("ALTER TABLE task_embeddings ALTER COLUMN embedding TYPE vector(4096) USING NULL::vector(4096)")

    # Step 4: Indexing
    # Note: Vector indexing (HNSW/IVFFlat) is omitted for now to avoid
    # PostgreSQL dimension limits (2000) during CI/CD.
    # Exact nearest neighbor search will be used, which is sufficient for current scale.

    # Step 5: Standard B-tree index on task_id for fast lookups
    op.create_index(
        "ix_task_embeddings_task_id",
        "task_embeddings",
        ["task_id"],
        unique=False,
    )


def downgrade() -> None:
    # Remove indexes and table
    op.drop_index("ix_task_embeddings_task_id", table_name="task_embeddings")
    op.drop_table("task_embeddings")