# syntax=docker/dockerfile:1.7
# Multi-stage backend image — slim runtime, non-root user.

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install uv (Python toolchain — see CLAUDE.md §17)
RUN pip install --no-cache-dir uv==0.5.11

COPY pyproject.toml uv.lock ./
# --no-install-project: install deps only, skip building the local package.
# The app/ source is copied directly in the runtime stage and found via WORKDIR.
# This avoids hatchling trying to resolve readme = "../README.md" (outside context).
RUN uv sync --no-dev --frozen --no-install-project


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd --create-home --shell /bin/bash app
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --chown=app:app app ./app
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app docker-entrypoint.sh ./

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=5 \
    CMD curl --silent --fail http://127.0.0.1:8000/health || exit 1

CMD ["./docker-entrypoint.sh"]
