"""Shared pytest fixtures for the Smart Travel Planner backend.

HOW FIXTURES CONNECT TO THE APP
---------------------------------
FastAPI's dependency injection system is the key to testability. Instead of
mocking internals, we use app.dependency_overrides to swap out any Depends()
provider with a test double:

    app.dependency_overrides[get_session] = lambda: fake_session
    app.dependency_overrides[current_user] = lambda: test_user
    app.dependency_overrides[get_classifier] = lambda: FakeClassifier()

This means tests exercise the REAL route handler, the REAL middleware (CORS,
exception handlers), and the REAL Pydantic serialisation — only the side
effects (DB, LLM, ML model) are swapped out.

The httpx.AsyncClient + ASGITransport pattern:
    - No network socket is opened.
    - The full ASGI middleware stack is exercised (CORS, exception handlers).
    - Tests run at full speed (no DNS, no TCP handshake).
    - Exactly the same code path as a real HTTP request, minus the socket.

FIXTURE LIFECYCLE ACROSS STAGES
---------------------------------
Stage 1 (now):   api_client — the basic HTTP test client.
Stage 2:         settings_override, db_session — real async DB fixtures.
Stage 3:         fake_classifier — loads a minimal joblib stub.
Stage 4:         fake_embedder — returns fixed-length zero vectors.
Stage 5:         fake_cheap_llm, fake_strong_llm — canned JSON responses.
Stage 6:         sample_user, sample_user_token — pre-seeded auth fixtures.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import build_app


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Tell pytest-anyio to use asyncio (not trio).

    Scope=session means this is evaluated once for the entire test run.
    All async fixtures and tests in this session use the asyncio event loop.
    """
    return "asyncio"


@pytest_asyncio.fixture
async def api_client() -> AsyncIterator[AsyncClient]:
    """HTTP test client wired to a fresh FastAPI app instance.

    HOW IT WORKS
    -------------
    1. build_app() creates a new FastAPI instance complete with middleware,
       exception handlers, and routers — identical to what uvicorn runs.
    2. ASGITransport wraps the app so httpx speaks ASGI directly, with no
       network socket. Every request still traverses the full middleware stack.
    3. The lifespan context manager fires automatically when AsyncClient
       enters its context (app startup) and on exit (app shutdown).

    WHY build_app() NOT the module-level `app`
    -------------------------------------------
    The module-level `app` may have dependency overrides from a previous test
    still attached. build_app() returns a clean instance each time so tests
    are fully isolated from each other.

    EXAMPLE USAGE
    --------------
    async def test_health(api_client: AsyncClient) -> None:
        response = await api_client.get("/health")
        assert response.status_code == 200
    """
    # build_app() reads settings via get_settings(). In the test environment
    # the .env file is absent. Tests that need Settings must set the required
    # env vars before importing or call get_settings.cache_clear() + patch.
    #
    # For Stage 1 the health endpoint requires NO settings at runtime
    # (settings are only used inside lifespan, which is skipped when the
    # test overrides the lifespan — but here we let it run to test the real path).
    application = build_app()

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Stage 2 fixtures
# ---------------------------------------------------------------------------

# `settings_override` is kept as a null fixture so Stage 3+ tests that
# declare it as a parameter don't get a missing-fixture error.
# Tests that need a real DB are self-contained in tests/integration/ and
# manage their own engine/session setup via TEST_DATABASE_URL.


@pytest.fixture
def settings_override() -> None:
    """No-op fixture — real DB tests live in tests/integration/.

    Integration tests read TEST_DATABASE_URL from the environment and
    skip automatically if it is absent.  This fixture exists so that future
    Stage 3+ fixtures can declare it as a dependency without error.
    """
    return None
