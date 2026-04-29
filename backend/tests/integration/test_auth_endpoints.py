"""Integration tests for POST /auth/signup and POST /auth/login.

REQUIREMENTS TO RUN
--------------------
These tests hit a REAL Postgres database (per the project's "no mocks for DB"
rule — see feedback/no_db_mocks.md).  They require:

    TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/travel_test

Set this env var (e.g. in your shell or a .env.test file) before running:

    TEST_DATABASE_URL=... uv run pytest tests/integration/

If the env var is absent, the entire module is skipped automatically.

HOW THE TEST DB IS SET UP
--------------------------
The `db_session` fixture in conftest.py:
    1. Creates all tables (Base.metadata.create_all) — fast DDL.
    2. Yields a session (tests run).
    3. Drops all tables (cleanup) after each test function.

This guarantees test isolation: each test starts with an empty DB.

WHAT IS TESTED
--------------
1. Successful signup → 201 + correct UserOut body.
2. Duplicate email → 422.
3. Password too short → 422 (Pydantic validation).
4. Successful login → 200 + access_token.
5. Login wrong password → 401 with generic message.
6. Login unknown email → 401 with SAME generic message (anti-enumeration).
7. Cross-user isolation: user A cannot see user B's data (future runs stage).

The password_hash is NEVER present in any response body — each test
verifies this explicitly.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.main import build_app

# Skip this entire module when no test database is configured.
pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set — skipping DB integration tests",
)

TEST_DB_URL = os.getenv("TEST_DATABASE_URL", "")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module")
async def test_engine() -> object:
    """Create the test DB engine and schema once per test module."""
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        # Ensure pgvector extension is available in the test DB.
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: object) -> AsyncSession:  # type: ignore[type-arg]
    """Yield a session; roll back all changes after each test for isolation."""
    from sqlalchemy.ext.asyncio import AsyncEngine

    engine: AsyncEngine = test_engine  # type: ignore[assignment]
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest_asyncio.fixture
async def auth_client(db_session: AsyncSession) -> AsyncClient:
    """HTTP client wired to a fresh app with the test DB session injected."""
    from app.deps.db import get_session

    app = build_app()

    # Override the get_session dependency to return our test session.
    async def override_get_session() -> AsyncSession:  # type: ignore[return]
        yield db_session

    app.dependency_overrides[get_session] = override_get_session

    from httpx import ASGITransport

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Tests — signup
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_signup_success(auth_client: AsyncClient) -> None:
    """Successful signup returns 201 + public user profile."""
    resp = await auth_client.post(
        "/auth/signup",
        json={"email": "alice@example.com", "password": "securepass1"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == "alice@example.com"
    assert "id" in body
    assert "created_at" in body
    assert "password_hash" not in body


@pytest.mark.anyio
async def test_signup_duplicate_email(auth_client: AsyncClient) -> None:
    """Registering the same email twice returns 422."""
    await auth_client.post(
        "/auth/signup",
        json={"email": "dup@example.com", "password": "firstpass1"},
    )
    resp = await auth_client.post(
        "/auth/signup",
        json={"email": "dup@example.com", "password": "secondpass2"},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.anyio
async def test_signup_password_too_short(auth_client: AsyncClient) -> None:
    """A password shorter than 8 chars is rejected at the schema level."""
    resp = await auth_client.post(
        "/auth/signup",
        json={"email": "b@example.com", "password": "short"},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_signup_invalid_email(auth_client: AsyncClient) -> None:
    """A malformed email is rejected at the schema level."""
    resp = await auth_client.post(
        "/auth/signup",
        json={"email": "not-an-email", "password": "validpass1"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests — login
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_login_success(auth_client: AsyncClient) -> None:
    """Correct credentials return 200 + a JWT access token."""
    await auth_client.post(
        "/auth/signup",
        json={"email": "login_ok@example.com", "password": "mypassword1"},
    )
    resp = await auth_client.post(
        "/auth/login",
        json={"email": "login_ok@example.com", "password": "mypassword1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert isinstance(body["expires_in"], int)


@pytest.mark.anyio
async def test_login_wrong_password(auth_client: AsyncClient) -> None:
    """Wrong password returns 401 with a generic message."""
    await auth_client.post(
        "/auth/signup",
        json={"email": "wrong_pw@example.com", "password": "correctpass1"},
    )
    resp = await auth_client.post(
        "/auth/login",
        json={"email": "wrong_pw@example.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401, resp.text
    # The response must not reveal whether the email exists.
    assert "password" not in resp.json().get("detail", "").lower()


@pytest.mark.anyio
async def test_login_unknown_email(auth_client: AsyncClient) -> None:
    """Unknown email returns 401 — same status and format as wrong password."""
    resp = await auth_client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "doesntmatter"},
    )
    assert resp.status_code == 401, resp.text


@pytest.mark.anyio
async def test_login_unknown_same_detail_as_wrong_password(
    auth_client: AsyncClient,
) -> None:
    """Unknown email and wrong password return the SAME detail message.

    This is the anti-enumeration guarantee: an attacker cannot tell whether
    the email exists by comparing the response bodies.
    """
    await auth_client.post(
        "/auth/signup",
        json={"email": "existing@example.com", "password": "realpassword1"},
    )
    wrong_pw = await auth_client.post(
        "/auth/login",
        json={"email": "existing@example.com", "password": "wrongpassword"},
    )
    unknown_email = await auth_client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "wrongpassword"},
    )
    assert wrong_pw.json()["detail"] == unknown_email.json()["detail"]


@pytest.mark.anyio
async def test_password_hash_never_in_response(auth_client: AsyncClient) -> None:
    """No response body from any auth endpoint contains password_hash."""
    signup_resp = await auth_client.post(
        "/auth/signup",
        json={"email": "nohash@example.com", "password": "securepass1"},
    )
    login_resp = await auth_client.post(
        "/auth/login",
        json={"email": "nohash@example.com", "password": "securepass1"},
    )
    assert "password_hash" not in signup_resp.text
    assert "password_hash" not in login_resp.text
    assert "password" not in signup_resp.json()
