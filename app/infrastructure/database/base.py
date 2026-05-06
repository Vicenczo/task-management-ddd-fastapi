"""
SQLAlchemy Declarative Base.

Single source of truth for all ORM model metadata.
All ORM models must inherit from `Base`.

Why a custom Base over plain DeclarativeBase:
  - Centralized __repr__ for debugging.
  - Future hooks (e.g., soft-delete mixin) can go here
    without touching individual models.
"""
from sqlalchemy.orm import DeclarativeBase, MappedColumn


class Base(DeclarativeBase):
    """
    Project-wide SQLAlchemy declarative base.

    All ORM table models inherit from this class.
    This is intentionally thin — no business logic lives here.
    """

    def __repr__(self) -> str:
        """
        Generic repr that shows table name and primary key.
        Useful for debugging without inspecting every model.
        """
        pk_col: MappedColumn | None = next(
            (c for c in self.__table__.columns if c.primary_key), None
        )
        pk_val = getattr(self, pk_col.name, "?") if pk_col is not None else "?"
        return f"<{self.__class__.__name__} pk={pk_val}>"