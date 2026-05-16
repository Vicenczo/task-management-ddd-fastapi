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
    # IF NOT EXISTS prevents error if extension already enabled
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
        # VECTOR(4096) — llama3 embedding dimension
        # pgvector registers this type after CREATE EXTENSION
        sa.Column(
            "embedding",
            sa.Text(),  # Placeholder; actual type set via raw SQL below
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
    # Cannot use sa.Column(Vector(4096)) directly in create_table because
    # pgvector type is only recognized AFTER the extension is created.
    # Using raw ALTER TABLE ensures correct type.
    op.execute("ALTER TABLE task_embeddings ALTER COLUMN embedding TYPE vector(4096) USING NULL::vector(4096)")

    # Step 4: Create IVFFlat index for fast cosine similarity search
    # lists=100 is suitable for tables up to ~1M rows
    # Increase lists as data grows (rule: sqrt(row_count))
    op.execute(
        "CREATE INDEX ix_task_embeddings_embedding_cosine "
        "ON task_embeddings "
        "USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
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
    # Note: we do NOT drop the vector extension — other tables may use it