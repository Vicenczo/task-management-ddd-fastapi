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
    # Using raw ALTER TABLE ensures correct type for llama3 embeddings
    op.execute("ALTER TABLE task_embeddings ALTER COLUMN embedding TYPE vector(4096) USING NULL::vector(4096)")

    # Step 4: Create HNSW index for fast cosine similarity search
    # FIXED: Switched from ivfflat to hnsw to support >2000 dimensions (Llama 3 uses 4096)
    op.execute(
        "CREATE INDEX ix_task_embeddings_embedding_cosine "
        "ON task_embeddings "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    # Step 5: Standard B-tree index on task_id for lookups
    op.create_index(
        "ix_task_embeddings_task_id",
        "task_embeddings",
        ["task_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_task_embeddings_task_id", table_name="task_embeddings")
    op.drop_index("ix_task_embeddings_embedding_cosine", table_name="task_embeddings")
    op.drop_table("task_embeddings")