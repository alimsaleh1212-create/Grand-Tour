"""Chat router — the user-facing agent entry point.

Implemented in Stage 6.

Endpoints (planned):
    POST /chat
        auth: required (Depends(current_user))
        body: ChatRequest
        response: ChatResponse, status 200
        side effects:
            * Creates an AgentRun row scoped to current_user.
            * Invokes the LangGraph agent (3 tools, two-model pipeline).
            * Persists one ToolCall row per tool invocation.
            * Schedules a background webhook delivery if webhook_url is
              provided OR the user has a default channel configured.
        errors:
            401 — missing/invalid token
            400 — empty question, malformed webhook URL
            500 — irrecoverable agent failure (logged, generic detail)

The webhook never breaks the user-facing response — delivery happens via
FastAPI BackgroundTasks and its failure is logged + persisted on the run.
"""
