"""Smart Travel Planner backend package.

The `app` package is the FastAPI service root. Submodule layout:

    core/     pydantic-settings, structured logging, JWT/bcrypt helpers,
              the AppError exception hierarchy.
    db/       async SQLAlchemy engine + session factory and ORM models
              (User, AgentRun, ToolCall, Embedding).
    schemas/  Pydantic request/response models for HTTP boundaries.
    routers/  FastAPI APIRouter modules — one per resource group.
    services/ business logic that the routers orchestrate.
    deps/     FastAPI Depends() providers — DB session, current user,
              ML model handle, vector store handle, agent executor.
    ml/       runtime-side ML loader (joblib via lifespan singleton).
    rag/      runtime-side RAG pipeline (loader, chunker, embedder, store).
    agent/    LangGraph state machine, prompts, tools, security guards.
    webhook/  outbound delivery (Discord/Slack adapters + retry publisher).

Entry point: `app.main:app`.
"""
