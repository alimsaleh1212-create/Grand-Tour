"""DB session dependency — yields one AsyncSession per HTTP request.

HOW THIS FITS INTO THE REQUEST LIFECYCLE
------------------------------------------
FastAPI resolves Depends() providers BEFORE calling the route handler body.
For every protected route that declares:

    session: Annotated[AsyncSession, Depends(get_session)]

FastAPI calls get_session(request) as a context manager:
    1. `async with sessionmaker() as session:` — opens a session (NOT a
       connection — the connection opens lazily on the first query).
    2. The route handler runs with the session injected.
    3. On normal return: nothing special (the service already committed).
    4. On exception: the async context manager closes the session (which
       implicitly rolls back any uncommitted changes).

READING app.state.SessionLocal
--------------------------------
`request.app.state.SessionLocal` is set during lifespan startup in
`app/main.py`.  Using `request.app.state` (not a module global) means:
    * The session factory is guaranteed to be initialised BEFORE any
      request is served (lifespan runs first).
    * Tests can override the factory via `app.dependency_overrides[get_session]`
      without touching module-level state.

WHY NOT `yield session` INSIDE try/finally
-------------------------------------------
`async_sessionmaker` used as an async context manager (`async with sm() as s`)
already handles cleanup correctly — it calls `session.close()` on exit whether
or not an exception was raised.  Adding a manual try/finally would be redundant.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield one AsyncSession scoped to the current HTTP request.

    The session is opened from the app.state.SessionLocal factory that was
    created during lifespan startup.  It is automatically closed when the
    route handler finishes (or if an exception propagates out of it).

    HOW COMMITS WORK
    -----------------
    Services call `await session.commit()` explicitly after each write
    operation.  The session does NOT auto-commit.  If the route handler
    raises AFTER a successful commit, the committed data stays in the DB
    (expected behaviour — the write succeeded).  If it raises BEFORE a
    commit, the rollback on session close discards the partial write.

    Usage in a route:
        @router.post("/thing")
        async def create_thing(
            session: Annotated[AsyncSession, Depends(get_session)],
            ...
        ) -> ThingOut:
            return await thing_service.create(session, ...)
    """
    SessionLocal = request.app.state.SessionLocal
    async with SessionLocal() as session:
        yield session


# Convenience type alias — routes declare this instead of the full Depends().
# Usage:  def my_route(db: DBSession) -> ...:
DBSession = Annotated[AsyncSession, Depends(get_session)]
