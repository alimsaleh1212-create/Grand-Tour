# CLAUDE.md — Smart Travel Planner

Combined behavioural + engineering standards for this project. Synthesised from
the AIE Bootcamp brief (`resources/Week4_Project_Smart_Travel_Planner .pdf`),
the original CLAUDE.md, and the *Engineering Standards Companion Guide*. Follow
automatically on every file you create or modify.

> **Engineering is the discipline of writing code that other people can change
> without fear.** — Hasan, Companion Guide

---

## Part I — How to Think

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- **Defend every line.** If you cannot explain in one sentence why a file,
  function, import, or dependency exists, remove it or understand it first.
  Never commit black-box AI-generated code you cannot read line by line.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- Remove imports/variables/functions that **your** changes made unused — nothing more.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

For multi-step tasks, state a brief plan up front:

```
1. [step] → verify: [check]
2. [step] → verify: [check]
```

Each stage in `plan.md` ends with an explicit validation gate. Do not advance
until the gate is green.

---

## Part II — Architecture Patterns (the Companion Guide)

These nine patterns are not optional. They reinforce each other: async needs DI
to manage shared resources cleanly; DI needs lifespan singletons to know what
to inject; singletons need a typed Settings class to decide what to load;
errors need types so a tool failure has a shape; tests need DI to mock
dependencies.

### 5. Async All the Way Down

**Every route, tool, and external call is `async`. No blocking I/O in the
request path.**

The agent loop is almost entirely I/O — it waits for Gemini, Postgres, weather
APIs, FX APIs, webhooks. Python has one event loop per process; one blocking
call freezes every other in-flight request.

```python
# ✗ Looks fine. It is not.
@app.post("/chat")
async def chat(question: str):
    weather = requests.get(WEATHER_URL).json()      # blocks
    flights = requests.get(FLIGHTS_URL).json()      # blocks
    return ...

# ✓ Real async. Real concurrency.
@app.post("/chat")
async def chat(question: str):
    async with httpx.AsyncClient(timeout=10.0) as http:
        weather, flights = await asyncio.gather(
            http.get(WEATHER_URL),
            http.get(FLIGHTS_URL),
        )
    ...
```

**Pitfalls (each one ships to production at least once per cohort):**

- `time.sleep` in async code → use `await asyncio.sleep`.
- `requests` anywhere in a request path → replace with `httpx`.
- CPU-bound work (large `model.predict`, big JSON parse) inside the event loop
  → wrap in `await asyncio.to_thread(...)`. **The travel-style classifier
  prediction is light, but persist this habit so heavier models don't trap
  you later.**
- Always pass a `timeout=` to `httpx.AsyncClient` — a hung connection hangs
  the whole request indefinitely.

### 6. Dependency Injection — No Globals

**Declare what you need. Let FastAPI hand it to you.**

Globals are untestable, leak across requests, and hide initialisation order.
FastAPI's `Depends()` is the cleanest DI in any Python web framework.

```python
# deps/db.py
async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session

# deps/auth.py
async def current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    return await load_user_from_token(token, session)

# deps/ml_model.py — singleton, populated in lifespan
def get_classifier(request: Request) -> ClassifierBundle:
    return request.app.state.classifier

# routers/chat.py
@router.post("/chat")
async def chat(
    payload: ChatRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    classifier: ClassifierBundle = Depends(get_classifier),
) -> ChatResponse:
    ...
```

Auth is a dependency that other dependencies can themselves depend on.
Sessions are scoped to the request via the `yield` — they open and close
automatically. In tests:
`app.dependency_overrides[get_classifier] = lambda: FakeClassifier()` — no
monkey-patching, no source edits.

### 7. Singletons via Lifespan

Some objects exist exactly once per process. Build them on startup, attach
them to `app.state`, dispose on shutdown, expose them via dependencies.

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.engine = create_async_engine(settings.async_database_url)
    app.state.classifier = load_classifier(settings.model_path)
    app.state.embedder = OllamaEmbedder(settings.ollama_base_url)
    app.state.gemini_cheap = build_cheap_client(settings)
    app.state.gemini_strong = build_strong_client(settings)
    yield
    await app.state.engine.dispose()
    await app.state.embedder.aclose()

app = FastAPI(lifespan=lifespan)
```

**Rule of thumb:**

| Lifetime           | Mechanism                          | Examples                                                |
| ------------------ | ---------------------------------- | ------------------------------------------------------- |
| Per process        | lifespan + `app.state`             | DB engine, ML model, embedder, Gemini clients, vector store handle |
| Per request        | `yield` in a `Depends()`           | DB session, transaction, current user                   |
| Per call           | nothing                            | values computed from inputs                             |

### 8. Caching — `lru_cache` and TTL Caches Where They Pay Off

The wrong cache is worse than no cache. Each cache below has an explicit
invalidation policy.

| Subject                       | Mechanism                                       | Why                                          | Invalidation                       |
| ----------------------------- | ----------------------------------------------- | -------------------------------------------- | ---------------------------------- |
| `Settings`                    | `@lru_cache(maxsize=1)`                         | Read env once at startup                     | Process restart                    |
| Gemini cheap/strong client    | `@lru_cache(maxsize=1)`                         | Auth + HTTP session expensive                | Process restart                    |
| Ollama `httpx.AsyncClient`    | `@lru_cache(maxsize=1)`                         | Connection-pool reuse                        | Process restart; closed in lifespan |
| ML classifier (joblib)        | Loaded in lifespan → `app.state.classifier`     | Loading per request is the named antipattern | Redeploy                           |
| Open-Meteo weather            | `cachetools.TTLCache(maxsize=512, ttl=600)` + `asyncio.Lock` | "Beirut weather is the same for 10 min" | TTL; key = `(lat, lon, date)`      |
| exchangerate.host FX          | `TTLCache(maxsize=128, ttl=3600)`               | Rates barely move in an hour                 | TTL; key = `(base, quote, date)`   |
| Amadeus flight quotes         | `TTLCache(maxsize=128, ttl=3600)`               | Same query within an hour ≈ same answer      | TTL; key = `(origin, dest, date)`  |
| RAG search result             | **Not cached**                                  | Different queries embed differently          | n/a — and the README says so       |
| LLM call result               | **Not cached**                                  | Synthesis depends on full state              | n/a                                |

**Implementation rule — thundering herd:** TTL caches in async code need an
`asyncio.Lock` with a double-check inside the lock. Otherwise 100 concurrent
"weather in Tokyo" requests miss simultaneously and all hit the API.

```python
weather_cache = TTLCache(maxsize=512, ttl=600)
weather_lock = asyncio.Lock()

async def get_weather(lat: float, lon: float, date: str) -> dict:
    key = (lat, lon, date)
    if key in weather_cache:
        return weather_cache[key]
    async with weather_lock:
        if key in weather_cache:          # double-check
            return weather_cache[key]
        result = await fetch_weather(lat, lon, date)
        weather_cache[key] = result
        return result
```

Caches live in **one** module per subject (the module that owns the resource),
never scattered. Document every TTL choice in the README — "10 minutes" is a
decision, not a default.

**Do not** `lru_cache` anything taking mutable args, anything that should
expire, or any function whose cache key is not its inputs (e.g. depends on
current time).

### 9. Configuration — `pydantic-settings`, Not Magic Strings

One `Settings` class. Every value typed. Missing required values fail at
startup. The rest of the codebase imports from `Settings` — never from
`os.environ` directly.

```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",          # typo in .env → error at startup
    )

    # required
    google_api_key: str = Field(..., min_length=1)
    jwt_secret: str = Field(..., min_length=32)
    postgres_password: str = Field(..., min_length=1)

    # required with sensible defaults
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_user: str = "travel"
    postgres_db: str = "travel"
    ollama_base_url: str = "http://ollama:11434"
    embed_model: str = "nomic-embed-text"
    embed_dim: int = 768
    gemini_cheap_model: str = "gemini-2.5-flash"
    gemini_strong_model: str = "gemini-2.5-pro"
    cors_origins: list[str] = ["http://localhost:5173"]

    @property
    def async_database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

**`extra="forbid"` is mandatory.** A typo (`GOOGEL_API_KEY`) must crash at
startup, not silently leave a `None` for two weeks.

Tests construct `Settings(google_api_key="test", ...)` directly — no env
variables required.

### 10. Type Hints, Pydantic, and the Boundary

**Validate at the edges. Trust your types inside.**

| Boundary                                | Pydantic model                                   |
| --------------------------------------- | ------------------------------------------------ |
| HTTP request body                       | `ChatRequest`, `LoginRequest`, `SignUpRequest`   |
| HTTP response body                      | `ChatResponse`, `LoginResponse`, `RunDetail`     |
| Agent tool input                        | `RetrieveQuery`, `ClassifyInput`, `LiveConditionsQuery` |
| Agent tool output                       | `RetrieveResult`, `ClassifyResult`, `LiveConditions` |
| LLM structured output                   | `response_schema=...` with a Pydantic model      |
| Webhook payload                         | `DiscordPayload`, `SlackPayload`                 |
| DB rows                                 | SQLAlchemy models; convert to Pydantic at the API boundary if serialising |

```python
class ClassifyInput(BaseModel):
    destination_name: str = Field(..., min_length=1, max_length=120)
    features: DestinationFeatures

class ClassifyResult(BaseModel):
    label: Literal["Adventure", "Relaxation", "Culture", "Budget", "Luxury", "Family"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    all_probabilities: dict[str, float]

async def classify_style(args: ClassifyInput) -> ClassifyResult:
    # args is already valid. Just do the work.
    ...
```

Once a value crosses the boundary as a validated model, **no inner function
re-checks `isinstance(x, dict)` or `if not x: return None`**. The 80%-defence,
20%-logic function is the antipattern.

Type hints are required on every function signature. `mypy --strict` runs in
pre-commit and CI.

### 11. Errors, Retries, and Failure Isolation

Three layers — you need all three.

**Layer 1 — Timeouts.** Every external call gets a timeout. No exceptions.

```python
async with httpx.AsyncClient(timeout=10.0) as client:
    r = await client.get(url)
```

**Layer 2 — Retries with backoff (transient only).** Use `tenacity`. Retry on
network / timeout / 5xx; **never** on 4xx (it'll fail the same way forever).

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    reraise=True,
)
async def fetch_weather(lat: float, lon: float) -> dict:
    ...
```

**Layer 3 — Failure isolation in the agent loop.** A tool failure must **not**
crash the agent. Return a structured `ToolError` so the LLM can reason about
the failure.

```python
class ToolError(BaseModel):
    error: str
    retryable: bool

async def live_conditions(args: LiveConditionsQuery) -> LiveConditions | ToolError:
    try:
        return await fetch_live(args)
    except httpx.HTTPStatusError as e:
        return ToolError(error=f"upstream {e.response.status_code}", retryable=False)
    except (httpx.TimeoutException, httpx.NetworkError) as e:
        return ToolError(error=f"unreachable: {e}", retryable=True)
```

This is what `safe_run()` on `BaseTool` enforces for every tool — exceptions
become `ToolResult(ok=False, error=...)`, never propagate into the LangGraph
loop.

**What never to do:**

- Bare `except:` or `except Exception: pass`. Catch specific types.
- Retry without a max-attempt cap (locks up your event loop).
- Let the webhook failing break the user-facing response. Webhook failure is
  logged; the API still returns the trip plan.
- Leak stack traces / file paths to clients. Trace goes to logs only.

### 12. Code Hygiene

**Project layout — one concern per file.** A 600-line `main.py` is a sign no
one is in charge of structure.

```
backend/app/
    main.py             # FastAPI app, lifespan, mount routers — that's it
    core/               # settings, logging, security, exceptions
    db/                 # session, base, models/
    schemas/            # Pydantic request/response per resource
    routers/            # auth.py, chat.py, runs.py, health.py
    services/           # business logic
    deps/               # Depends() providers
    ml/, rag/, agent/, webhook/   # subsystem packages
```

**File names describe content.** Banned: `utils.py`, `helpers.py`, `misc.py`,
`stage1.py`, `thing.py`. If you can't pick a descriptive name, the file is
doing too many unrelated things — split it.

**Every endpoint lives in an `APIRouter`** — never in `main.py`. Adopt this on
day one; the cost is zero, the benefit is that endpoint #20 doesn't require
a restructure.

**Logging — never `print()`.** Use a structured logger; every log line is a
JSON object with named fields.

```python
import structlog
log = structlog.get_logger()

async def run_agent(query: str, user_id: int) -> AgentResult:
    log.info("agent.run.start", user_id=user_id, query_length=len(query))
    try:
        result = await agent.ainvoke({"input": query})
        log.info("agent.run.success", user_id=user_id, tools=result["tools"])
        return result
    except Exception:
        log.exception("agent.run.failure", user_id=user_id)
        raise
```

Levels: `DEBUG` (internals) · `INFO` (milestones) · `WARNING` (recoverable) ·
`ERROR` (failed op) · `CRITICAL` (service down). Never log passwords, JWTs,
PII, or API keys.

### 13. Tests — At Least the Critical Path

You will not get to 100% coverage and you should not try. You **must** have a
small set of tests that runs in seconds, fails loudly when something
important breaks, and runs automatically on every commit.

**Three categories cover most of what matters:**

1. **Pydantic schemas.** Cheap, high-value. Test both valid and invalid input.
   ```python
   def test_classify_input_rejects_unknown_label():
       with pytest.raises(ValidationError):
           ClassifyResult(label="freezing", confidence=0.5, all_probabilities={})
   ```

2. **Tools — mock the LLM, mock the API, test the logic.** Each tool should
   be testable without calling the real Gemini or hitting the real Open-Meteo.
   ```python
   async def test_live_conditions_handles_api_failure(monkeypatch):
       async def boom(*a, **kw): raise httpx.TimeoutException("t/o")
       monkeypatch.setattr("app.agent.tools.live_conditions._fetch_weather", boom)
       result = await live_conditions(args)
       assert isinstance(result, ToolError)
       assert result.retryable is True
   ```

3. **End-to-end — one happy path through the whole agent.** With Gemini and
   external APIs mocked, run a full request and assert the right tools fire
   and the response is well-formed.

**Coverage targets** (per stage gate in `plan.md`):

- Critical paths (auth service, routers): ≥ 95%
- Tools, agent graph nodes: ≥ 90%
- Overall backend: ≥ 80%

Tests run in CI on every push (see `infra/github-actions/ci.yml`). A test that
doesn't run is a test that doesn't exist.

---

## Part III — Domain-Specific Rules (Smart Travel Planner)

### 14. LLM Provider — Google Gemini

This project uses the **Google Gemini API** exclusively. Do **not** import
`anthropic` or `openai` SDKs.

- Client: `google-generativeai` Python SDK.
- Auth: `GOOGLE_API_KEY` env var, loaded via `Settings`.
- **Two tiers:**
  - `cheap = gemini-2.5-flash` — extraction, query rewriting, routing,
    tool-arg generation. Fires many times per request.
  - `strong = gemini-2.5-pro` — final synthesis only. Fires **once** per
    request.
- Use `response_mime_type="application/json"` with `response_schema=PydanticModel`
  for structured extraction. **Never** parse free-form LLM text with regex or
  string splitting.
- **Separate prompt layers.** System prompt = role + format + invariants
  (static); user prompt = the varying query only.
- Cache both clients with `@lru_cache(maxsize=1)`.
- Every call has `max_output_tokens`, `timeout`, and tenacity retries on
  transient errors.
- Log prompts and responses with sensitive fields scrubbed.
- Persist token usage and cost per `tool_call` row.

### 15. LLM Input Security — Prompt Injection Prevention

User input flows into Gemini prompts. Every Stage-5 tool must enforce these
eight rules. The implementation lives in `backend/app/agent/security.py`.

1. **Sanitize before format().** Call `_sanitize_query()` on every user-supplied
   string before interpolating it into any prompt template (normalises
   whitespace, strips control chars, truncates, removes `system:` / `assistant:`
   leak triggers).
2. **Delimit user content.** Wrap user text in `<user_input>...</user_input>`
   tags in every prompt template. Never embed raw user text adjacent to
   instructions.
3. **Sanitize LLM string outputs before re-use.** Any string from a cheap-model
   output that flows into another prompt or a tool argument runs through
   `_sanitize_feature_string()`.
4. **`max_output_tokens` on every Gemini call.** Caps exfiltration attempts.
5. **No `eval()` / `exec()` on LLM output.** Ever. Tool args are JSON-parsed
   and Pydantic-validated; failures return a structured error to the LLM for
   retry.
6. **Log suspicious patterns.** Patterns (`ignore previous`, `you are now`,
   `system prompt`, `\n\nHuman:`) are logged at WARNING but not rejected.
   Rate-limiting at the FastAPI layer handles abuse.
7. **Pydantic is the fence.** Every tool input is a Pydantic model;
   structurally invalid args never reach the implementation.
8. **Tool allowlist.** The agent rejects any tool name outside
   `{retrieve_destinations, classify_style, live_conditions}`, even if the
   LLM hallucinates one.

### 16. Agent — LangGraph + `BaseTool` ABC

Every tool subclasses `BaseTool` (`backend/app/agent/tools/base.py`):

```python
class BaseTool(ABC, Generic[InputT, OutputT]):
    name: ClassVar[str]
    input_schema: ClassVar[type[BaseModel]]
    output_schema: ClassVar[type[BaseModel]]

    @abstractmethod
    async def run(self, args: InputT) -> OutputT: ...

    async def safe_run(self, raw_args: dict) -> ToolResult[OutputT]:
        """Validate raw_args → run() → wrap exceptions. Never raises."""
        ...
```

`safe_run()` is the **only** entry point the LangGraph node calls. It
validates with `input_schema`, calls `run()`, and wraps exceptions as
`ToolResult(ok=False, error=...)`. Validation failures return a structured
error to the LLM for retry — never as an exception to the user.

The agent registry is a dict `{tool.name: tool}` built from the `BaseTool`
subclass list. Adding a tool requires zero changes elsewhere.

LangGraph topology (`backend/app/agent/graph.py`):
`sanitize → plan → tool_loop → synthesise → persist`. The strong model fires
once, in the synthesise node.

### 17. ML Lifecycle — Defensible Choices Only

- **Raw data is read-only.** Never modify `ml/data/raw/`.
- **Processed data** → `ml/data/processed/`.
- **Models** → `ml/models/<name>_v<version>.joblib`.
- **Feature pipeline** is an sklearn `Pipeline` with `ColumnTransformer` doing
  imputation + scaling + one-hot encoding **inside** the pipeline. Never
  pre-transform the data — that's how leakage gets in.
- **Justify every feature.** Be ready to explain why each kept feature
  matters and why each dropped feature was dropped.
- **Always compare against a baseline** — `DummyClassifier(strategy="stratified")`
  is the floor. A metric without a baseline says nothing.
- **Cross-validation, not a single split.** `StratifiedKFold(k=5)` for
  evaluation **and** inside `GridSearchCV`.
- **Reproducibility.** `random_state=42` on every stochastic call. Hash the
  dataset and record the hash in `results.csv`.
- **Class imbalance.** Report counts; pick `class_weight="balanced"` vs.
  SMOTE deliberately and justify; report per-class metrics.
- **Track results.** `ml/results/results.csv` gets one row per experiment:
  timestamp, model, params, accuracy ± std, macro-F1 ± std, per-class metrics,
  baseline comparison, dataset hash, joblib path.
- **Notebooks are for exploration.** All reusable logic lives in `ml/src/`.
- **Labeling rules are mandatory.** `ml/data/labeling/labeling_rules.md`
  describes the rule for every label — written before training.

### 18. RAG — Document Every Choice

- **Ingestion is offline batch.** `rag/scripts/ingest.py` (CLI), not a request
  handler. Re-runnable; idempotent on `(source, chunk_index)`.
- **Embeddings are local.** Ollama service (`nomic-embed-text`, 768-dim).
  The pgvector column dimension and `Settings.embed_dim` must match.
  Switching models requires an Alembic migration.
- **Chunking strategy is a documented decision** (default: 500 chars / 50
  overlap, sentence-aware). The README explains why.
- **Retrieval strategy is documented** (cosine, top-k=5, similarity threshold).
  Three hand-written queries with retrieved-chunk screenshots demonstrate
  quality.
- **RAG search results are not cached** — different queries embed
  differently; the cache would pollute. The README explicitly says so.

### 19. FastAPI Patterns

- Every endpoint has a Pydantic model for its request body **and** another
  for its response — no raw `dict` bodies.
- Every endpoint lives in a router file under `routers/<resource>.py`.
- **Never** return `200 OK` with `{"error": "..."}` in the body. Raise
  `HTTPException` with the correct status code:

| Code | Use when                                                            |
| ---- | ------------------------------------------------------------------- |
| 200  | Success with body                                                   |
| 201  | Created a new resource                                              |
| 400  | Client sent malformed data                                          |
| 401  | Authentication missing or invalid                                   |
| 403  | Authenticated but not permitted                                     |
| 404  | Resource does not exist (also: User A asking for User B's run)      |
| 422  | Well-formed but semantically invalid (Pydantic returns automatically) |
| 500  | Unhandled server-side error (generic message — no traces leaked)    |

- Authorization filters every list/get by `user_id`. User A cannot read User B's
  runs. Cross-user isolation is tested.
- Webhook delivery runs in a `BackgroundTasks` after the response is built.
  Webhook failure is logged and persisted as `webhook_status` on the run; it
  does **not** break the response.

---

## Part IV — Toolchain & Hygiene

### 20. Python Code Style

Toolchain: **Black** (line length 88) · **isort** (`profile = "black"`) ·
**flake8** (max 88) · **mypy --strict**.

- 4 spaces, never tabs.
- Double quotes for strings.
- Trailing commas in all multi-line structures.
- Type hints on every function signature.
- 2 blank lines between top-level definitions; 1 between methods.

Import order (blank line between groups):

```python
# 1. stdlib
import asyncio
from typing import AsyncIterator

# 2. third-party
import httpx
from fastapi import APIRouter, Depends

# 3. local
from app.core.settings import get_settings
from app.deps.db import get_session
```

### 21. Naming Conventions

| Element                       | Convention             | Example                |
| ----------------------------- | ---------------------- | ---------------------- |
| Variables, functions, modules | `snake_case`           | `fetch_destination()`  |
| Classes                       | `PascalCase`           | `RetrieveDestinations` |
| Constants                     | `UPPER_SNAKE_CASE`     | `MAX_OUTPUT_TOKENS`    |
| Private attributes            | `_leading_underscore`  | `self._client`         |
| Booleans                      | reads as a question    | `is_active`, `has_key` |
| Collections                   | plural                 | `chunks`, `tool_calls` |

Functions start with a verb: `get_`, `fetch_`, `load_`, `train_`, `save_`,
`validate_`, `process_`, `build_`, `run_`. No single-letter names except loop
counters (`i`, `j`) and lambdas.

### 22. Security — CRITICAL

- **Never** hardcode keys, tokens, passwords, or connection strings.
- All secrets flow through `Settings` (one place). No `os.getenv(...)`
  scattered across files.
- `.env` is in `.gitignore`. Commit `.env.example` with every required key
  and **fake placeholder values only**.
- If a secret is ever committed, **rotate it immediately**. Removing the
  commit from history is not enough — it persists in forks, clones, and CI
  logs.
- Required env vars: `GOOGLE_API_KEY`, `JWT_SECRET`, `POSTGRES_PASSWORD`.
  Optional: `AMADEUS_API_KEY`, `LANGCHAIN_API_KEY`, `DISCORD_WEBHOOK_URL`.
- Passwords hashed with bcrypt; never stored or logged in plaintext.
- JWTs in `Authorization: Bearer …` only — never in URLs or query params.
- Validate all user input at API boundaries with Pydantic.

### 23. Documentation (Google Style)

Every public module, class, and function has a docstring:

```python
async def classify_style(args: ClassifyInput) -> ClassifyResult:
    """Predict the travel-style label for a destination.

    Args:
        args: Validated destination features.

    Returns:
        Predicted label, confidence, and per-class probabilities.

    Raises:
        MLModelError: If the loaded classifier rejects the feature shape.
    """
```

Inline comments explain **why**, not **what**. Module docstrings describe
intended functionality and how the module interacts with neighbours.

### 24. Dependency Management with `uv`

This project uses `uv`. Do **not** use `pip` or `venv` directly.

```bash
uv sync                        # install prod + dev deps
uv sync --no-dev               # prod only (production image)
uv run pytest                  # run tests in the venv
uv run uvicorn app.main:app    # start FastAPI
uv add <package>               # add a prod dependency
uv add --dev <package>         # add a dev dependency
```

`pyproject.toml` is the single source of truth. **Pinned exact versions**
(`fastapi==0.115.6`). Never use `requirements.txt`. Always commit `uv.lock` —
reproducible builds depend on it.

```toml
[project]
dependencies = [...]           # production only

[dependency-groups]
dev = [...]                    # pytest, black, mypy — never in prod image
```

### 25. Pre-commit Pipeline

```
black → isort → flake8 → mypy → pytest → gitleaks
```

Configured in `.pre-commit-config.yaml`. Run `uv run pre-commit install` once
after cloning. Hooks must pass before any commit lands.

### 26. Git Hygiene

**Branch naming:** `<type>/<short-description>` — lowercase, hyphens, 2–4 words.

| Prefix      | Use for                |
| ----------- | ---------------------- |
| `feature/`  | New functionality      |
| `bugfix/`   | Bug fix                |
| `hotfix/`   | Urgent production fix  |
| `refactor/` | Code restructuring     |
| `docs/`     | Documentation only     |
| `test/`     | Tests added or updated |
| `chore/`    | Maintenance / tooling  |

Never commit directly to `main`.

**Commit messages — Conventional Commits:** `<type>(<scope>): <summary>`.
Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`,
`security`. Imperative mood, capitalise first letter, no trailing period,
≤ 72 chars. Example: `feat(agent): Add live_conditions tool with TTL cache`.

**PR rules:** title `[TYPE] Short imperative description`. ≤ 400 lines per PR.
**One concern per PR.** Required body sections: Summary · Changes · Testing ·
Screenshots (if applicable) · Checklist (style, self-review, tests, docs, no
secrets, no lint errors).

### 27. Docker & Deployment

- **One service, one container, one Dockerfile.** Backend and frontend are
  separate images.
- `docker-compose.yaml` orchestrates the whole stack: db (pgvector), ollama,
  ollama-init (one-shot model pull), backend, frontend, pgadmin.
- Services reference each other by service name (`http://backend:8000`,
  `http://ollama:11434`) — never hardcoded IPs.
- Named volumes for `postgres_data` and `ollama_models` — both survive
  restarts so the demo doesn't re-download a 270 MB model on every `up`.
- Healthchecks on db, ollama, backend. `depends_on: condition: service_healthy`
  so backend never starts before its dependencies are ready.
- Multi-stage Dockerfiles, slim base images, non-root user.
- **Deploy both pieces.** A backend without a frontend is not a finished
  project; both must be publicly reachable and pointing at each other.

### 28. README Requirements

The README is the front door. A reader should clone, set up, and run the
whole project without asking a single question.

**Required sections:**

1. Project name + one-paragraph description.
2. Architecture overview (with a diagram) — backend, frontend, db, ollama,
   external services.
3. Prerequisites — Docker, `uv`, Node 20.
4. Setup — clone, `cp .env.example .env`, fill keys.
5. How to run — `docker compose up` must be one of the commands.
6. Environment variables — every variable, purpose, required/optional.
7. Project structure — short tree.
8. **ML & RAG narrative** (consolidated into the root README per Stage 4
   note in `plan.md`):
   - Labeling-rules link.
   - Feature justifications & dropped-features rationale.
   - Model comparison table (3 classifiers + baseline, accuracy ± std,
     macro-F1 ± std, per-class).
   - Tuning rationale.
   - Chunk-size & overlap rationale.
   - Retrieval strategy (top-k, similarity threshold).
   - 3 RAG queries with retrieved-chunk screenshots.
   - Per-query cost breakdown (Gemini tokens × price).
   - LangSmith trace screenshot.
9. Deployment notes — live URLs (when deployed) and how to deploy.

**Do not include:** a full library list (that's `pyproject.toml`), a wall of
screenshots, or a full API reference (link to `/docs`).

---

## Pre-Review Checklist

Run through this before every PR. If you can't answer "yes" to all of it,
you have work to do.

- [ ] I can explain what every file does and why it is named that way.
- [ ] Every route, tool, and external call is async. No `requests`, no
      `time.sleep`, no blocking I/O in the request path.
- [ ] Every dependency (DB session, LLM client, current user, ML model) is
      declared with `Depends()`. No globals.
- [ ] Heavy resources (engine, classifier, embedder, Gemini clients) load once
      in lifespan and dispose on shutdown.
- [ ] `lru_cache` on deterministic helpers; TTL cache on at least one external
      call where it makes sense; thundering-herd lock present where needed.
- [ ] All config goes through `Settings`. No `os.getenv` outside it.
      `extra="forbid"` is set.
- [ ] Every external boundary (HTTP req/resp, tool input/output, LLM
      structured output, webhook payload) has a Pydantic model.
- [ ] Every external call has a timeout, tenacity retries with backoff
      (transient only), and structured error returns from tools.
- [ ] Code is split into modules by concern. Logging is structured. Linter and
      formatter run on every commit.
- [ ] Pydantic schemas, tool logic, and one e2e agent flow are tested. Tests
      run in CI.
- [ ] Every endpoint lives in an `APIRouter`, raises `HTTPException` with the
      correct status code; cross-user isolation is enforced and tested.
- [ ] LLM calls use `response_schema` with Pydantic; system prompt and user
      prompt are separated; every call has `max_output_tokens`.
- [ ] Prompt-injection guardrails (sanitize, delimit, log) are applied
      everywhere user text reaches a prompt.
- [ ] `random_state=42` set on every stochastic ML call. Baseline comparison
      reported. Cross-validation used.
- [ ] `.env`, `.venv`, model artefacts, and large data files are in
      `.gitignore`. No secrets in git. Secrets loaded from one config module.
- [ ] Each service has its own Dockerfile; `docker compose up` runs the whole
      stack from a clean machine.
- [ ] `uv` used for environments; `uv.lock` committed.
- [ ] No AI-generated code I cannot explain line by line.

---

*The reason production codebases feel different from tutorial code is not that
they use fancier libraries. It's that every part of the codebase respects the
same set of standards, and the parts compose because of it.*
