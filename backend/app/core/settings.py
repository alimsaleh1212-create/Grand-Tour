"""Application settings — pydantic-settings, single source of truth.

HOW THIS MODULE FITS INTO THE STARTUP FLOW
-------------------------------------------
1. The lifespan() function in app/main.py calls get_settings() first, before
   any other step.
2. pydantic-settings reads the .env file and validates every field.
3. If a required field is missing → ValidationError is raised HERE, at startup.
   The process refuses to start cleanly instead of failing mysteriously mid-request.
4. @lru_cache means this construction happens exactly ONCE per process.
   Every other module calls get_settings() and receives the same typed object.
5. Tests call get_settings.cache_clear() then construct Settings(...) directly
   with fake values — no actual .env file required in the test environment.

WHY pydantic-settings (not scattered os.getenv)
------------------------------------------------
- One place to look for every config value — no grepping through 12 files.
- Types enforced: POSTGRES_PORT="not_a_number" fails at startup, not later.
- SecretStr prevents passwords appearing in logs, repr(), or tracebacks.
- extra="forbid" makes a typo like GOOGEL_API_KEY raise an error instead of
  silently setting google_api_key=None for two weeks.
- IDE autocomplete works on settings.postgres_host; it doesn't work on dicts.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Typed, validated configuration loaded from environment variables.

    Field groups:
        App          — runtime mode, log level, CORS
        Postgres     — connection params (host/port/user/pass/db)
        Auth         — JWT signing, bcrypt cost
        LLM          — Gemini model names, output limits, retry policy
        Embeddings   — Ollama URL, model name, vector dimension
        RAG          — chunk size/overlap, retrieval top-k
        Live data    — optional Amadeus key for the flights tool
        Tracing      — LangSmith (env-gated, off by default)
        Webhook      — Discord/Slack URLs, delivery policy

    All fields have type annotations so mypy --strict passes.
    SecretStr fields never appear in logs, repr(), or error messages.
    """

    model_config = SettingsConfigDict(
        # Reads from .env in the current working directory.
        # In Docker, .env is mounted via docker-compose env_file.
        env_file=".env",
        env_file_encoding="utf-8",
        # CRITICAL: a typo like GOOGEL_API_KEY raises ValidationError at startup
        # instead of silently leaving google_api_key as None for two weeks.
        extra="forbid",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    # Controls SQL echo, docs URL visibility, and log verbosity defaults.
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    # Comma-separated list read by pydantic-settings as list[str].
    # The Vite dev server runs on 5173; add your deployed frontend URL in prod.
    cors_origins: list[str] = Field(default=["http://localhost:5173"])

    # ── Postgres ─────────────────────────────────────────────────────────────
    # Each component is its own field so that POSTGRES_HOST can be "db"
    # (Docker service name) or "localhost" (local dev) without touching the
    # others. The async_database_url computed property assembles the full DSN.
    postgres_user: str = "travel"
    # SecretStr: the password is never printed in logs or tracebacks.
    # Call .get_secret_value() only when building the connection URL.
    postgres_password: SecretStr = Field(...)
    postgres_db: str = "travel"
    # In docker-compose this is the service name "db"; locally it's "localhost".
    postgres_host: str = "db"
    postgres_port: int = 5432

    # ── Auth ─────────────────────────────────────────────────────────────────
    # JWT_SECRET must be a long random string. Generate with:
    #   python -c "import secrets; print(secrets.token_hex(32))"
    # Changing it invalidates all existing tokens (forces re-login).
    jwt_secret: SecretStr = Field(...)
    jwt_algorithm: str = "HS256"
    # How long access tokens are valid. There are no refresh tokens in this
    # project (deferred to optional Stage O5), so keep this reasonably long
    # for the demo — 60 min is fine.
    jwt_access_ttl_minutes: int = 60
    # bcrypt cost factor. 12 is the 2024 industry default (~250 ms on typical
    # hardware). Lower this to 4 in tests to avoid slow fixture setup.
    bcrypt_rounds: int = 12

    # ── LLM (Google Gemini) ───────────────────────────────────────────────────
    # GOOGLE_API_KEY is required. Without it the backend refuses to start.
    # This is intentional — the whole product is useless without a functioning LLM.
    google_api_key: SecretStr = Field(...)
    # Cheap model fires many times per request (extraction, routing, tool-arg
    # generation). Strong model fires ONCE (final synthesis). See agent/graph.py.
    gemini_cheap_model: str = "gemini-2.5-flash"
    gemini_strong_model: str = "gemini-2.5-pro"
    # Hard cap on output length. Prevents exfiltration attempts and runaway costs.
    gemini_max_output_tokens: int = 2048
    # Tenacity retry policy for transient Gemini errors (5xx, network timeouts).
    # Applied in agent/llm_clients.py.
    llm_max_retries: int = 3
    llm_retry_delay: float = 1.0  # seconds; exponential backoff multiplied from this

    # ── Embeddings (Ollama) ───────────────────────────────────────────────────
    # Full URL including protocol — httpx.AsyncClient needs it as base_url.
    # In docker-compose this resolves via the service name "ollama".
    # For local dev outside Docker: http://localhost:11434
    ollama_base_url: str = "http://ollama:11434"
    ollama_embed_model: str = "nomic-embed-text"
    # CRITICAL: embed_dim must match the pgvector column dimension defined in
    # the Alembic migration (db/models/embedding.py). Changing the model
    # requires a new migration to ALTER the vector column size.
    embed_dim: int = 768

    # ── RAG ──────────────────────────────────────────────────────────────────
    # Chunk size/overlap rationale is documented in the root README.
    # 500 chars / 50 overlap is the default; the ingest CLI can override these.
    default_chunk_size: int = 500
    default_chunk_overlap: int = 50
    # How many chunks to retrieve from pgvector per query.
    # Higher = more context for Gemini, but more tokens and higher cost.
    retrieval_top_k: int = 5

    # ── Live conditions APIs ──────────────────────────────────────────────────
    # Open-Meteo (weather) and exchangerate.host (FX) need no keys.
    # Amadeus (flights) is OPTIONAL. When absent, live_conditions returns:
    #   {"flights": {"available": false, "reason": "key not configured"}}
    # The agent reasons about missing data rather than raising an error.
    amadeus_api_key: SecretStr | None = None
    amadeus_api_secret: SecretStr | None = None

    # ── Tracing (LangSmith) ───────────────────────────────────────────────────
    # Set LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY=<key> to enable.
    # When false (the default), no traces are sent — safe for offline demos.
    langchain_tracing_v2: bool = False
    langchain_api_key: SecretStr | None = None
    langchain_project: str = "smart-travel-planner"

    # ── Webhook (Discord / Slack) ─────────────────────────────────────────────
    # Both are optional. The publisher fires whichever URL is set, or skips the
    # step entirely. Failure is logged and stored; it never breaks the response.
    discord_webhook_url: str | None = None
    slack_webhook_url: str | None = None
    webhook_timeout_seconds: float = 5.0
    webhook_max_retries: int = 1  # 1 retry = 2 total attempts

    # ── Computed properties ───────────────────────────────────────────────────

    @computed_field  # type: ignore[prop-decorator]
    @property
    def async_database_url(self) -> str:
        """Assemble the asyncpg DSN from individual components.

        Why decomposed: each component (host, port, db) can be overridden
        independently by environment variable. docker-compose sets POSTGRES_HOST
        to the service name; local dev sets it to localhost; CI uses a test DB.
        Only ONE place ever does this string formatting.
        """
        pw = self.postgres_password.get_secret_value()
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{pw}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-level Settings singleton.

    @lru_cache(maxsize=1) ensures Settings() is constructed exactly once per
    process regardless of how many modules import this function.

    Test isolation pattern:
        get_settings.cache_clear()
        # then construct Settings directly with test values
    """
    settings = Settings()
    # Log at DEBUG (not INFO) so production logs aren't flooded on every restart.
    # The log includes non-secret fields only — no passwords or API keys.
    logger.debug(
        "settings.loaded",
        extra={
            "env": settings.app_env,
            "log_level": settings.log_level,
            "postgres_host": settings.postgres_host,
            "postgres_db": settings.postgres_db,
            "ollama_base_url": settings.ollama_base_url,
            "embed_dim": settings.embed_dim,
            "tracing_enabled": settings.langchain_tracing_v2,
        },
    )
    return settings
