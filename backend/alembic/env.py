"""Alembic migration environment — wires async SQLAlchemy + our models.

HOW ALEMBIC USES THIS FILE
----------------------------
When you run `alembic upgrade head`, Alembic:
    1. Reads alembic.ini to find this env.py (script_location = alembic).
    2. Imports this file.
    3. Calls run_migrations_online() (or run_migrations_offline()).
    4. run_migrations_online() runs all pending migration scripts in order.

HOW ASYNC SUPPORT WORKS
-------------------------
SQLAlchemy's async engine cannot run migrations synchronously — Alembic
expects a synchronous `connection.execute()` API.  The pattern used here:

    async def run_async_migrations() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(do_run_migrations)

`conn.run_sync(fn)` calls `fn(sync_conn)` on a synchronous connection
wrapped from the async one — this is the SQLAlchemy-recommended adapter
for Alembic in async projects.

HOW target_metadata DRIVES AUTOGENERATE
-----------------------------------------
`target_metadata = Base.metadata` tells Alembic's autogenerate command
(`alembic revision --autogenerate`) to compare the live DB schema against
all tables declared in `Base.metadata`.

For `Base.metadata` to include all tables, every model file must have been
imported BEFORE this line executes.  Importing `app.db.models` triggers
`app/db/models/__init__.py` which imports User, AgentRun, ToolCall, Embedding.

HOW THE DB URL IS INJECTED
----------------------------
alembic.ini has `sqlalchemy.url =` (empty).  We override it at runtime with
`Settings.async_database_url` via `config.set_main_option()`.  This means:
    * No credentials are ever hardcoded in alembic.ini.
    * alembic.ini can be committed safely.
    * The same .env file that drives the app also drives migrations.

NOTE ON PGVECTOR EXTENSION
----------------------------
The very first migration (`versions/001_initial.py`) calls:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
before creating any table with a `vector(N)` column.  Without this,
Postgres would reject the column type with "type vector does not exist".
Alembic autogenerate does NOT include extension creation — it is added
manually to the first migration.
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.settings import get_settings

# Import all models so Base.metadata is fully populated before autogenerate.
import app.db.models  # noqa: F401  — side-effect import; populates Base.metadata
from app.db.base import Base

# ---------------------------------------------------------------------------
# Alembic configuration
# ---------------------------------------------------------------------------
config = context.config

# Wire up stdlib logging from alembic.ini if a config file was provided.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The metadata object that autogenerate compares against the live DB schema.
target_metadata = Base.metadata

# Inject Vault secrets into os.environ BEFORE constructing Settings.
# pydantic-settings reads os.environ at construction time, and the required
# fields (postgres_password, jwt_secret, google_api_key) live in Vault in
# Docker.  Without this, Alembic crashes with ValidationError because the
# vault-loader in app.main never runs during `alembic upgrade head`.
_vault_addr = os.environ.get("VAULT_ADDR")
_vault_token = os.environ.get("VAULT_TOKEN")
if _vault_addr and _vault_token:
    from app.core.vault import load_vault_secrets

    load_vault_secrets(_vault_addr, _vault_token)

# Inject the DB URL from settings (overrides the empty sqlalchemy.url in ini).
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.async_database_url)


# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------


def do_run_migrations(connection: Connection) -> None:
    """Run all pending migrations on a synchronous connection.

    This function is passed to `conn.run_sync()` which adapts the async
    connection to the synchronous API that Alembic expects.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # compare_type=True: detect column type changes in autogenerate.
        compare_type=True,
        # render_as_batch: required for SQLite; harmless for Postgres.
        render_as_batch=False,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations via run_sync().

    The engine is created fresh here (not from app.state) because Alembic
    runs as a CLI tool, not inside the FastAPI lifespan.  The settings are
    read from .env via get_settings() just as in the app.
    """
    engine = create_async_engine(settings.async_database_url)
    async with engine.begin() as conn:
        await conn.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    """Entry point for online migration mode (default).

    Alembic calls this when not in `--sql` (offline) mode.
    We bridge into asyncio using asyncio.run().
    """
    asyncio.run(run_async_migrations())


def run_migrations_offline() -> None:
    """Emit migration SQL without connecting to the database.

    Useful for generating SQL scripts to review before applying.
    Run with: alembic upgrade head --sql > migration.sql

    HOW IT WORKS
    -------------
    Alembic calls context.execute() to write SQL to stdout instead of
    sending it to a live connection.  The URL is still needed for dialect
    detection (Postgres syntax vs SQLite, etc.).
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


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
