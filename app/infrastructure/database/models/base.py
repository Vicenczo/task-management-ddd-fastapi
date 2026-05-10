"""
SQLAlchemy Declarative Base for all ORM models.

Separation of concerns:
  - Domain models (app/domain/models/) = pure Python dataclasses, zero ORM knowledge.
  - ORM models (here)                  = infrastructure detail, knows nothing about business logic.

The mapper layer (mappers.py, to be added later) will translate between the two.

UUID primary keys are used across all tables for:
  - Distributed system compatibility (no ID conflicts on merge/shard).
  - Security (non-guessable IDs).
  - Alignment with domain Entity.id (UUID v4).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    """Returns current UTC datetime with timezone info. Always use this, never datetime.utcnow()."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """
    Shared declarative base for all ORM models.

    All tables inherit:
      - id          : UUID primary key (non-sequential, v4).
      - created_at  : Immutable creation timestamp (UTC).
      - updated_at  : Mutable last-update timestamp (UTC), updated on every write.
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )