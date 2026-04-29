"""HTTP routers — one APIRouter per resource group.

Per CLAUDE.md §22: "Every endpoint lives in a router file (routers/<resource>.py)
grouped by resource, not in main.py."

Modules:
    health.py   GET /health  — liveness probe; no dependencies.
    auth.py     POST /auth/signup, POST /auth/login.
    chat.py     POST /chat — auth-protected; kicks off an agent run.
    runs.py     GET /runs, GET /runs/{id} — auth-protected; user-scoped.

Each router declares its own `prefix` and `tags`, validates inputs through
schema models, raises `HTTPException` on errors (never `200 OK` with an
error body), and never instantiates clients/sessions itself — those come
through `Depends(...)`.
"""
