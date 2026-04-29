"""Stage 1 validation gate — health endpoint test.

This test is the minimum viable signal that the whole Stage 1 implementation
is wired together correctly. It exercises:

    1. build_app() factory → FastAPI instance
    2. lifespan startup sequence (logging → settings → DB engine stubs)
    3. CORSMiddleware registration
    4. Exception handler registration
    5. Router include (health.router)
    6. GET /health → HealthResponse Pydantic model → JSON serialisation
    7. ASGITransport + httpx.AsyncClient test fixture

If any link in this chain is broken (bad import, missing router, wrong
Pydantic field), this test fails immediately with a clear error.

HOW TO RUN
-----------
    cd backend
    uv run pytest tests/test_smoke.py -v

Expected output:
    tests/test_smoke.py::test_health_returns_ok PASSED
"""

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_health_returns_ok(api_client: AsyncClient) -> None:
    """GET /health returns 200 with body {"status": "ok"}.

    This is the Stage 1 gate test. If startup fails (missing env vars,
    import error, lifespan exception), httpx will raise an error before
    the response is checked, making the failure immediately visible.
    """
    response = await api_client.get("/health")

    assert (
        response.status_code == 200
    ), f"Expected 200, got {response.status_code}. Body: {response.text}"
    assert response.json() == {"status": "ok"}, f"Unexpected body: {response.json()}"


@pytest.mark.anyio
async def test_health_has_json_content_type(api_client: AsyncClient) -> None:
    """GET /health returns application/json content type.

    Verifies that FastAPI is serialising the Pydantic response model
    correctly, not returning a plain string or HTML.
    """
    response = await api_client.get("/health")
    assert "application/json" in response.headers["content-type"]


@pytest.mark.anyio
async def test_unknown_route_returns_404(api_client: AsyncClient) -> None:
    """Unknown routes return 404 (FastAPI default behaviour).

    Ensures the router is not accidentally catching all paths, and that
    the exception handler chain doesn't accidentally swallow 404s.
    """
    response = await api_client.get("/this-route-does-not-exist")
    assert response.status_code == 404
