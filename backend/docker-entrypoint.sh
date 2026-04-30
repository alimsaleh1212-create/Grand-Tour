#!/bin/sh
# Run Alembic migrations then start uvicorn.
# Using sh (not bash) for compatibility with python:3.12-slim.
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
