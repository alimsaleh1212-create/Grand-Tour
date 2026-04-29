"""Domain exceptions — AppError hierarchy.

HOW EXCEPTIONS FLOW THROUGH THE STACK
---------------------------------------
Every exception in this hierarchy follows the same path:

    1. Raised inside a service or tool (e.g. services/auth_service.py,
       app/agent/tools/live_conditions.py).
    2. Caught by an exception_handler registered in app/main.py.
    3. The handler logs the full detail SERVER-SIDE (logger.warning / error).
    4. The handler returns a JSONResponse with a SAFE, GENERIC message
       to the client — no stack traces, file paths, or internal state.

HTTP status code mapping (each subclass documents its own):
    AuthError            → 401 Unauthorized
    PermissionError      → 403 Forbidden
    NotFoundError        → 404 Not Found
    DomainValidationError → 422 Unprocessable Entity
    RAGError             → 500 Internal Server Error
    MLModelError         → 500 Internal Server Error
    ToolError subclasses → NOT raised into HTTP layer (see note below)
    WebhookDeliveryError → NOT raised into HTTP layer (see note below)

WHY A HIERARCHY (not just plain Exception)
-------------------------------------------
- Catching specific types (not bare `except`) lets handlers respond
  differently to auth failures vs. not-found vs. internal errors.
- `isinstance` checks in tests are clean: `assert isinstance(exc, AuthError)`.
- Adding a new exception type is one line; wiring its HTTP code is one more.
"""


class AppError(Exception):
    """Base class for all domain errors in this application.

    Never raise AppError directly — raise a specific subclass so the
    exception handler in main.py can return the correct HTTP status code.
    """


# ── HTTP-layer exceptions (raised into the router, translated to responses) ──


class AuthError(AppError):
    """Raised by: core/security.py (bad/expired JWT), services/auth_service.py.

    Triggered when:
      - JWT signature verification fails.
      - Token has expired.
      - A user tries to log in with the wrong password.

    HTTP mapping: 401 Unauthorized.
    Client message: "Authentication required." (generic — never expose why).
    """


class PermissionError(AppError):
    """Raised by: services/ when the authenticated user does not own a resource.

    Example: User A calls GET /runs/{id} where the run belongs to User B.
    The handler returns 404 (not 403) to avoid leaking that the run exists.

    HTTP mapping: 403 Forbidden (or 404 where leaking existence is a risk).
    """


class NotFoundError(AppError):
    """Raised by: services/ when a DB lookup returns None.

    The str(exc) value is passed through to the client detail field because
    it is always safe (e.g. "Run not found" — no internal paths or IDs).

    HTTP mapping: 404 Not Found.
    """


class DomainValidationError(AppError):
    """Raised by: services/ for semantic validation the Pydantic model cannot express.

    Pydantic/FastAPI handle structural errors (wrong type, missing field)
    automatically with HTTP 422. This exception is for business-rule errors
    that require domain knowledge to check (e.g. "departure date is in the past").

    HTTP mapping: 422 Unprocessable Entity.
    """


# ── Agent tool exceptions (NOT raised into HTTP layer) ───────────────────────
#
# Tool exceptions are caught by BaseTool.safe_run() in agent/tools/base.py.
# safe_run() wraps them as ToolResult(ok=False, error=...) and returns them
# to the LangGraph loop. The LLM then reasons about the failure (e.g. "flights
# unavailable — I'll omit that section") rather than crashing the request.
# These exceptions NEVER reach the exception handlers in main.py.


class ToolError(AppError):
    """Base for agent tool failures.

    Subclass for the specific failure mode so the LLM's retry logic
    can distinguish retryable (network timeout) from non-retryable (bad key).
    """


class ToolValidationError(ToolError):
    """Raised when Pydantic rejects the LLM's tool arguments.

    The structured error is returned to the LLM so it can correct its
    argument schema and retry. Marked retryable=True in ToolResult.
    """


class ExternalAPIError(ToolError):
    """Raised when an external API call fails after all tenacity retries.

    Covers: weather (Open-Meteo), FX (exchangerate.host), flights (Amadeus),
    Gemini. Whether it's retryable depends on whether it was a 5xx or a
    network error vs. a 4xx (4xx will always fail the same way — don't retry).
    """


class ToolUnavailableError(ToolError):
    """Raised when a tool cannot run due to configuration, not a network error.

    Example: live_conditions calls the Amadeus flights API but
    settings.amadeus_api_key is None. The tool returns a structured
    "flights unavailable" response instead of raising into the agent loop.
    """


# ── Infrastructure exceptions (bubble to HTTP 500) ───────────────────────────


class RAGError(AppError):
    """Raised by: app/rag/* when the embedder or pgvector store fails.

    Examples: Ollama is unreachable, pgvector upsert fails mid-ingestion.

    HTTP mapping: 500 Internal Server Error.
    Client message: "An internal error occurred." (never leak internals).
    """


class MLModelError(AppError):
    """Raised by: app/ml/classifier_loader.py when the joblib fails to load
    or predict() returns an unexpected shape.

    HTTP mapping: 500 Internal Server Error.
    """


# ── Fire-and-forget exception (never reaches HTTP layer) ─────────────────────


class WebhookDeliveryError(AppError):
    """Raised by: app/webhook/publisher.py when all retries are exhausted.

    This exception does NOT bubble to the router. The chat endpoint fires
    the webhook via FastAPI BackgroundTasks AFTER the response is sent.
    Failure is:
      1. Logged at ERROR level with the webhook URL and attempt count.
      2. Persisted as webhook_status="failed" on the AgentRun DB row.
    The user always receives their trip plan regardless of webhook outcome.
    """
