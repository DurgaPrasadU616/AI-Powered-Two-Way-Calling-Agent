"""Alembic environment — async-aware, reads DATABASE_URL from pydantic Settings."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context

# ── Load application config & models ─────────────────────────────────────────
from app.core.config import get_settings
from app.db.base import Base

# Import every model so they register with Base.metadata before autogenerate
from app.db.models import (  # noqa: F401
    Admin,
    Call,
    CallEvent,
    CallExtractedData,
    CallSummary,
    CallTurn,
    Contact,
)
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# ── Alembic config object ─────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
target_metadata = Base.metadata


# ── Offline mode ──────────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    """Run migrations in offline mode (no DB connection needed for SQL output)."""
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode (async) ───────────────────────────────────────────────────────
def _do_run_migrations(connection) -> None:  # type: ignore[type-arg]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    connectable = create_async_engine(settings.DATABASE_URL, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
