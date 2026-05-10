"""
Alembic environment configuration for async SQLAlchemy.

Key design choices:
  1. DATABASE URL is read from app.core.config.settings (single source of truth).
     The sqlalchemy.url in alembic.ini is intentionally left as placeholder.
  2. All ORM models are imported via app.infrastructure.database.models
     so that Base.metadata contains every table for autogenerate.
  3. run_async_migrations() uses AsyncEngine — required for asyncpg driver.
  4. include_schemas=True ensures schema-level changes are tracked.
"""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings

# --- Import ALL models so Base.metadata is fully populated ---
# This import is the critical step — without it, autogenerate sees 0 tables.
from app.infrastructure.database.models import Base  # noqa: F401, E402
from app.infrastructure.database.models import (  # noqa: F401, E402
    ProjectMemberModel,
    ProjectModel,
    TaskModel,
    UserModel,
)

# --- Alembic Config object (alembic.ini access) ---
config = context.config

# --- Logging setup from alembic.ini [loggers] section ---
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- Target metadata for autogenerate ---
target_metadata = Base.metadata

# --- Override sqlalchemy.url with value from settings (single source of truth) ---
# Converts pydantic PostgresDsn to plain string required by SQLAlchemy
config.set_main_option("sqlalchemy.url", str(settings.DB_URL))


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Generates SQL scripts without a live DB connection.
    Useful for generating migration scripts to review before applying.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Configure and run migrations on an existing sync connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,      # detect column type changes
        compare_server_default=True,  # detect server default changes
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations using an async engine (required for asyncpg).

    Creates a temporary engine — separate from the app's main engine
    to avoid lifecycle conflicts during migration runs.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # No pooling for migrations — single connection
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online (live DB) migrations."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()