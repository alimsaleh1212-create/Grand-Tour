"""Business-logic services.

Routers stay thin; the actual work lives here. Services:
    * receive validated Pydantic input and an AsyncSession,
    * orchestrate ORM operations and downstream calls (agent, webhook),
    * raise `AppError` subclasses on domain failure (which routers convert
      to HTTP),
    * return ORM rows or domain dataclasses — NEVER raw dicts.

Modules:
    auth_service.py    signup, login, password verification, token issue
    user_service.py    fetch_by_id, fetch_by_email
    run_service.py     create_run, append_tool_call, finalise_run
    webhook_service.py orchestrates delivery via webhook.publisher
    token_logger.py    helper for accumulating cheap/strong Gemini tokens
                       across a single AgentRun
"""
