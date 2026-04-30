"""FastAPI application entry point — the root of the whole backend.

═══════════════════════════════════════════════════════════════════════════════
COMPLETE STARTUP FLOW (read this before touching anything)
═══════════════════════════════════════════════════════════════════════════════

  process starts (uvicorn runs `app.main:app`)
       │
       ▼
  build_app() executes at import time
       │  creates FastAPI(lifespan=lifespan) — lifespan NOT called yet
       │  registers CORS middleware
       │  registers exception handlers
       │  includes routers
       │  returns the `app` object
       │
  uvicorn starts accepting connections
       │
       ▼
  lifespan(app) begins  ← first HTTP request triggers this
       │
       ├─ Step 1: setup_logging()
       │     → installs JSON formatter on root logger
       │     → all subsequent steps are now observable
       │
       ├─ Step 2: get_settings() (already @lru_cache'd — reads .env)
       │     → if any required key is missing → ValidationError → process exits
       │     → if extra="forbid" detects a typo → ValidationError → process exits
       │
       ├─ Step 3: create_async_engine(settings.async_database_url)
       │     → builds the SQLAlchemy connection pool
       │     → pool_pre_ping=True validates connections before use
       │     → echo=True in dev prints every SQL statement (useful for debugging)
       │     → NO connections are opened yet — pool is lazy
       │
       ├─ Step 4: async_sessionmaker(engine)
       │     → factory that produces AsyncSession objects
       │     → stored on app.state.SessionLocal so get_session() dep can reach it
       │     → expire_on_commit=False keeps objects usable after commit
       │
       ├─ Step 5: placeholder singletons for later stages
       │     app.state.classifier = None   (Stage 3: joblib ML model)
       │     app.state.embedder   = None   (Stage 4: httpx client → Ollama)
       │     app.state.gemini_cheap = None (Stage 5: Gemini Flash client)
       │     app.state.gemini_strong = None(Stage 5: Gemini Pro client)
       │
       ▼
  yield  ← app is live; uvicorn starts routing requests
       │
       │  [every request goes through the COMPLETE REQUEST FLOW below]
       │
  shutdown signal received
       │
       ├─ await engine.dispose()   → drains and closes the DB connection pool
       └─ embedder.aclose()        → closes the httpx session (Stage 4)

═══════════════════════════════════════════════════════════════════════════════
COMPLETE REQUEST FLOW (every HTTP request follows this path)
═══════════════════════════════════════════════════════════════════════════════

  HTTP request arrives
       │
       ▼
  CORSMiddleware
       │  checks Origin header against settings.cors_origins
       │  if allowed: mirrors the Origin header back (browser proceeds)
       │  if denied: omits CORS headers (browser blocks the request)
       │
       ▼
  Router dispatch
       │  FastAPI matches method + path → route handler function
       │  e.g. POST /chat → routers/chat.py::chat_endpoint (Stage 6)
       │
       ▼
  Depends() resolution (runs before the handler body)
       │
       ├─ get_session()
       │     → opens AsyncSession from app.state.SessionLocal
       │     → yields it to the handler
       │     → closes/rolls back on exit (even if the handler raises)
       │
       ├─ current_user()    (Stage 2)
       │     → reads Authorization: Bearer <token>
       │     → decodes JWT (core/security.py)
       │     → fetches User row from DB
       │     → raises AuthError → 401 if invalid
       │
       ├─ get_classifier()  (Stage 3)
       │     → returns app.state.classifier (loaded ONCE in lifespan)
       │     → same object every request; no disk I/O per request
       │
       └─ get_agent()       (Stage 5)
             → builds LangGraph executor with bound tools + LLM clients
       │
       ▼
  Route handler runs
       │  calls services/ (business logic)
       │  returns a Pydantic model
       │
       ▼
  FastAPI serialises response
       │  Pydantic model → JSON → HTTP response
       │
       ▼
  Exception? AppError subclass
       │  caught by exception_handler registered below
       │  full detail logged server-side (logger.warning / error)
       │  client receives only: {"detail": "<safe generic message>"}
       │  stack trace NEVER reaches the client

═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import pathlib

from app.core.exceptions import (
    AppError,
    AuthError,
    DomainValidationError,
    NotFoundError,
    PermissionError,
)
from app.core.logging import setup_logging
from app.core.settings import get_settings
from app.db.session import create_engine, make_sessionmaker
from app.routers import auth, health

# Module-level logger — used only for lifespan events. Route-level loggers
# are declared in their own modules with logging.getLogger(__name__).
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build all singletons on startup; dispose them cleanly on shutdown.

    Why lifespan instead of @app.on_event("startup"):
        on_event is deprecated since FastAPI 0.93. lifespan is an async
        context manager — the `yield` cleanly separates startup from shutdown,
        and Python guarantees the finally-equivalent block always runs (even if
        startup raises, the engine is disposed).

    Why app.state instead of module globals:
        Module globals are constructed at import time, before settings are read.
        app.state is populated inside lifespan, AFTER settings validate — so
        the right values drive every singleton. Tests can also call
        app.dependency_overrides[get_session] = ... to swap singletons without
        touching module state.
    """
    settings = get_settings()

    # ── Step 1: Logging (must be first — everything after is logged) ──────────
    setup_logging(settings.log_level)
    logger.info("startup.begin", extra={"env": settings.app_env})

    # ── Step 2: Settings already validated by get_settings() call above ───────
    # If a required env var was missing, get_settings() raised ValidationError
    # before we reached this line. The process would have exited cleanly.
    # By the time we are here, all settings are typed and safe to use.

    # ── Step 3: Async DB engine (connection pool) ─────────────────────────────
    # create_engine() (from db/session.py) wraps create_async_engine with the
    # project-standard settings: pool_pre_ping=True (validates connections
    # before use — prevents stale-connection errors after DB restarts) and
    # echo=True only in development (SQL logging).
    # The pool is lazy — no connections are opened until the first query.
    engine = create_engine(settings)
    app.state.engine = engine
    logger.info("startup.db_engine_ready", extra={"host": settings.postgres_host})

    # ── Step 4: Session factory ────────────────────────────────────────────────
    # make_sessionmaker() (from db/session.py) wraps async_sessionmaker with
    # expire_on_commit=False so ORM objects remain usable after commit without
    # keeping the session open for a second SELECT.
    # Stored on app.state.SessionLocal so deps/db.py:get_session() can reach it.
    SessionLocal = make_sessionmaker(engine)
    app.state.SessionLocal = SessionLocal

    # ── Step 5: Singletons for Stage 3, 4, and 5 ─────────────────────────────

    # Stage 3: ML classifier — loaded once from joblib; never per-request.
    from app.ml.classifier_loader import load_classifier

    app.state.classifier = load_classifier(
        pathlib.Path(settings.ml_model_path)
    )

    # Stage 4: GeminiEmbedder singleton — avoids re-configuring the Gemini
    # SDK and re-creating the lru_cache entry on every embedding request.
    from app.rag.embedder import get_embedder

    embedder = get_embedder(
        api_key=settings.google_api_key.get_secret_value(),
        model=settings.gemini_embed_model,
        embed_dim=settings.embed_dim,
    )
    app.state.embedder = embedder

    # Stage 5: VectorStore, Gemini LLM clients, tools, and compiled agent.
    import httpx as _httpx

    from app.agent.graph import AgentDeps, build_agent
    from app.agent.llm_clients import get_cheap_client, get_strong_client
    from app.agent.tools.classify_style import ClassifyStyleTool
    from app.agent.tools.live_conditions import LiveConditionsTool
    from app.agent.tools.retrieve_destinations import RetrieveDestinationsTool
    from app.rag.store import VectorStore

    api_key = settings.google_api_key.get_secret_value()
    cheap_llm = get_cheap_client(api_key, settings.gemini_max_output_tokens)
    strong_llm = get_strong_client(api_key, settings.gemini_max_output_tokens)
    app.state.gemini_cheap = cheap_llm
    app.state.gemini_strong = strong_llm

    vector_store = VectorStore(SessionLocal)
    live_http = _httpx.AsyncClient(timeout=15.0)
    app.state.live_http = live_http

    agent_deps = AgentDeps(
        cheap_llm=cheap_llm,
        strong_llm=strong_llm,
        retriever=RetrieveDestinationsTool(embedder=embedder, store=vector_store),
        classifier=ClassifyStyleTool(classifier=app.state.classifier),
        live_tool=LiveConditionsTool(http=live_http),
    )
    app.state.agent = build_agent(agent_deps)

    logger.info("startup.complete")

    # ── Yield: app is live ─────────────────────────────────────────────────────
    # Everything above runs BEFORE the first request is handled.
    # Everything below runs AFTER the last request, on shutdown.
    yield

    # ── Shutdown ───────────────────────────────────────────────────────────────
    logger.info("shutdown.begin")

    # Drain the DB connection pool — waits for in-flight queries to complete,
    # then closes all connections. Without this, the DB sees stale connections.
    await engine.dispose()

    # Close the embedder's httpx session (Stage 4).
    await app.state.embedder.aclose()

    # Close the live-conditions shared httpx session (Stage 5).
    if hasattr(app.state, "live_http"):
        await app.state.live_http.aclose()

    logger.info("shutdown.complete")


def build_app() -> FastAPI:
    """Construct and configure the FastAPI application.

    Why a factory function (not module-level `app = FastAPI(...)`):
        Tests call build_app() to get a fresh app instance with a clean
        app.state and no dependency overrides leaking between tests.
        Uvicorn imports `app` at module level — `app = build_app()` at the
        bottom of this file gives it the instance it needs.
    """
    settings = get_settings()

    application = FastAPI(
        title="Smart Travel Planner",
        description=(
            "AI-powered travel planning agent. "
            "Combines RAG (pgvector), an ML travel-style classifier, "
            "and live conditions (weather + FX + flights) into a "
            "LangGraph agent that synthesises personalised trip plans."
        ),
        version="0.1.0",
        lifespan=lifespan,
        # Hide /docs and /redoc in production to reduce attack surface.
        # In development these are invaluable for exploring the API.
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url=None,
    )

    # ── CORS ───────────────────────────────────────────────────────────────────
    # CORSMiddleware runs BEFORE every router. It reads the Origin header from
    # the browser's preflight (OPTIONS) or simple request and either:
    #   - mirrors Origin back as Access-Control-Allow-Origin (browser proceeds)
    #   - omits the header (browser blocks the request with a CORS error)
    # The allowed origins come from settings.cors_origins, loaded from .env.
    # In dev this is ["http://localhost:5173"] (Vite). In prod, add the deployed
    # frontend URL to CORS_ORIGINS in the environment.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,  # required for Authorization header to pass
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handlers ─────────────────────────────────────────────────────
    # Each handler follows the same pattern:
    #   1. Log the full detail server-side (for debugging).
    #   2. Return a JSONResponse with a SAFE, GENERIC client message.
    # The client NEVER sees stack traces, file paths, or internal state.
    # The HTTP status code is the machine-readable signal; detail is for humans.

    @application.exception_handler(AuthError)
    async def _auth_error(request: Request, exc: AuthError) -> JSONResponse:
        # Log at WARNING (not ERROR) — auth failures are expected (wrong password,
        # expired token). They're not bugs; they're normal user behaviour.
        logger.warning(
            "auth.error",
            extra={"path": str(request.url.path), "detail": str(exc)},
        )
        # Generic message — never tell the client whether the user exists.
        return JSONResponse(
            status_code=401, content={"detail": "Authentication required."}
        )

    @application.exception_handler(PermissionError)
    async def _permission_error(request: Request, exc: PermissionError) -> JSONResponse:
        logger.warning(
            "permission.error",
            extra={"path": str(request.url.path), "detail": str(exc)},
        )
        return JSONResponse(status_code=403, content={"detail": "Access denied."})

    @application.exception_handler(NotFoundError)
    async def _not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        # str(exc) is intentionally passed through — NotFoundError messages are
        # always safe (e.g. "Run not found"). No internal paths or IDs.
        return JSONResponse(
            status_code=404, content={"detail": str(exc) or "Not found."}
        )

    @application.exception_handler(DomainValidationError)
    async def _validation_error(
        request: Request, exc: DomainValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422, content={"detail": str(exc) or "Invalid request."}
        )

    @application.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        # Catch-all for any AppError subclass not handled above.
        # Log at ERROR — these are unexpected failures.
        logger.error(
            "app.error.unhandled",
            extra={"type": type(exc).__name__, "path": str(request.url.path)},
            exc_info=True,
        )
        return JSONResponse(
            status_code=500, content={"detail": "An internal error occurred."}
        )

    # ── Routers ────────────────────────────────────────────────────────────────
    # Each router lives in its own file, grouped by resource (not by HTTP method).
    # main.py NEVER defines endpoints directly — see CLAUDE.md §22.
    application.include_router(health.router)
    application.include_router(auth.router)  # prefix="/auth" set inside the router
    # Stage 6: application.include_router(chat_router,  prefix="/chat",  tags=["chat"])
    # Stage 6: application.include_router(runs_router,  prefix="/runs",  tags=["runs"])

    return application


# ── Module-level app instance ──────────────────────────────────────────────────
# Uvicorn imports this: `uvicorn app.main:app`
# Tests import build_app() directly to get a fresh instance per test.
app = build_app()
