# syntax=docker/dockerfile:1.7
# Multi-stage backend image — slim runtime, non-root user.
# Stage 1 will populate this; Stage 0 ships the skeleton only.

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install uv (Python toolchain — see CLAUDE.md §17)
RUN pip install --no-cache-dir uv==0.5.11

COPY pyproject.toml ./
# uv.lock will be added in Stage 1 once `uv sync` has been run locally.
# COPY uv.lock ./
RUN uv sync --no-dev --frozen || uv sync --no-dev


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Non-root user
RUN useradd --create-home --shell /bin/bash app
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --chown=app:app app ./app
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app alembic.ini ./

USER app
EXPOSE 8000

# Healthcheck targets the /health endpoint defined in app/main.py
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://127.0.0.1:8000/health', timeout=3).raise_for_status()" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
