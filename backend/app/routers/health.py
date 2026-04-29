"""Health-check router — GET /health.

HOW THIS ENDPOINT FITS INTO THE SYSTEM
----------------------------------------
Request lifecycle for GET /health:
    1. HTTP request arrives at uvicorn.
    2. CORSMiddleware checks the Origin header (no-op for same-origin or curl).
    3. FastAPI dispatches to this router via the prefix registered in main.py.
    4. health() runs — zero I/O, returns a Pydantic model.
    5. FastAPI serialises HealthResponse → {"status": "ok"}.
    6. docker-compose healthcheck reads this response to decide whether the
       backend service is ready before starting the frontend service.

WHY NO DB PING HERE
---------------------
The docker-compose healthcheck runs every 15 seconds and drives the
depends_on: condition: service_healthy gate. If we included a DB ping and
the DB was momentarily slow (e.g. running migrations), the healthcheck would
fail and docker-compose would restart the backend unnecessarily.

A /readyz endpoint that checks DB + Ollama connectivity can be added later
for observability tooling that expects a deep readiness probe.
"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Response body for GET /health.

    Using a Pydantic model (not a raw dict) enforces that the response schema
    is typed and appears correctly in the auto-generated OpenAPI docs at /docs.
    """

    status: str


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
    description="Returns 200 OK. Used by the Docker healthcheck.",
)
async def health() -> HealthResponse:
    """Return a static 200 OK response.

    Why async: FastAPI runs all route handlers on the event loop. Declaring
    this as `async def` is consistent with every other route in the project
    and costs nothing for a no-I/O handler.

    Why logger.debug (not info): This endpoint is polled every 15 seconds by
    the Docker healthcheck. Logging at INFO would produce 4 lines per minute
    of pure noise in production logs. DEBUG is filtered out by default.
    """
    logger.debug("health.check")
    return HealthResponse(status="ok")
