"""Async SQLAlchemy engine + session factory helpers.

HOW THIS MODULE FITS INTO THE STARTUP FLOW
-------------------------------------------
This module provides two helper functions used by `app/main.py`'s lifespan:

    lifespan(app):
        engine = create_engine(settings)          ← Step 3 in startup
        sessionmaker = make_sessionmaker(engine)  ← Step 4 in startup
        app.state.engine = engine
        app.state.SessionLocal = sessionmaker
        yield
        await engine.dispose()                    ← shutdown

The FastAPI dependency `get_session` in `deps/db.py` reads
`request.app.state.SessionLocal` and yields an AsyncSession per request.

WHY HELPER FUNCTIONS INSTEAD OF MODULE-LEVEL SINGLETONS
---------------------------------------------------------
The engine is built INSIDE lifespan, not at import time.  This ensures:
    1. Settings are fully validated before any connection is attempted.
    2. Tests can call build_app() multiple times without sharing an engine
       (each test gets its own isolation boundary).
    3. There are no module-level side effects — importing this module does
       not open any sockets or read any files.

CONNECTION POOL SETTINGS
-------------------------
pool_pre_ping=True
    Before handing a connection to a session, SQLAlchemy fires a cheap
    SELECT 1 probe.  If the DB restarted (e.g. during a rolling migration),
    the stale connection is discarded and a fresh one is opened.
    Without this, the first query after a DB restart would fail with a
    connection error that propagates to the user.

echo=settings.app_env == "development"
    Logs every SQL statement to stdout in dev.  Too noisy for staging/prod.
    Controlled by `app_env`, not a separate `DEBUG` flag, so there is only
    one place to change.

expire_on_commit=False
    After session.commit(), SQLAlchemy normally marks all attributes as
    expired so they reload from the DB on next access.  Disabling this lets
    route handlers return an ORM object from a service function without
    keeping the session open for a second query.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.settings import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Build an async SQLAlchemy engine from validated settings.

    Called once in lifespan.  The engine manages a connection pool but does
    NOT open any connections until the first session makes a query.

    Args:
        settings: The validated Settings singleton (from get_settings()).

    Returns:
        AsyncEngine with pool_pre_ping and optional SQL echo enabled.
    """
    return create_async_engine(
        settings.async_database_url,
        pool_pre_ping=True,
        echo=settings.app_env == "development",
    )


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build a session factory bound to the given engine.

    The factory is stored on `app.state.SessionLocal` and consumed by
    `deps/db.py:get_session()` on every request.

    Args:
        engine: The AsyncEngine built by `create_engine()`.

    Returns:
        An async_sessionmaker that produces AsyncSession objects.
    """
    return async_sessionmaker(
        engine,
        expire_on_commit=False,  # see module docstring for rationale
    )
