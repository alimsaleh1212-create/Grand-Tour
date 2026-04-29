"""Runs router — read-side history of agent runs.

Implemented in Stage 6.

Endpoints (planned):
    GET /runs
        auth: required
        response: list[AgentRunOut] (paginated, newest first)

    GET /runs/{run_id}
        auth: required
        response: AgentRunOut (with embedded tool_calls timeline)
        errors:
            404 — not found OR not owned by current_user (do NOT leak
                  existence to other users)

Authorisation is enforced by filtering every query on user_id ==
current_user.id; cross-user isolation is verified by tests in Stage 6.
"""
