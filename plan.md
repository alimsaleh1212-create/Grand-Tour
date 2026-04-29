# Smart Travel Planner — Strategic Plan

## Context

Greenfield build of a production-grade travel-planning agent that reads requirements from `resources/Week4_Project_Smart_Travel_Planner.pdf` and obeys engineering standards from `resources/CLAUDE.md`, `resources/mentor_guidelines.md`, and `resources/AIE_Bootcamp_Coding_Guidelines.pdf`. The starting point is a near-empty repo containing only a partial `docker-compose.yaml` (Postgres+pgvector and pgAdmin already declared) and the resources folder. We will plan the entire system, scaffold every file with descriptive docstrings, then implement stage-by-stage with mandatory validation between stages.

**Defining property:** the AI must work end-to-end (real synthesis, no concatenation) AND the surrounding code must be built like an engineer built it (async, DI, lifespan singletons, no globals, no blocking I/O, typed boundaries, tested critical paths). Both will be reviewed.

---

## High-Level Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│  React + Vite SPA  (frontend/)                                         │
│  - sign-in / chat / run-detail                                         │
└──────────────┬─────────────────────────────────────────────────────────┘
               │  HTTP + JWT                                              
┌──────────────▼─────────────────────────────────────────────────────────┐
│  FastAPI backend  (backend/app/)                                       │
│  routers → services → (agent | ml | rag | webhook | auth)              │
│  All async. DI via Depends(). Singletons via lifespan.                 │
└────┬──────────────┬────────────────┬──────────────────┬────────────────┘
     │              │                │                  │                 
┌────▼───┐   ┌──────▼─────┐   ┌──────▼──────┐   ┌──────▼──────────┐      
│ ML     │   │  RAG       │   │  Agent      │   │  Webhook        │      
│ joblib │   │  pgvector  │   │  LangGraph  │   │  Discord/Slack  │      
│ (1×    │   │  store     │   │  3 tools    │   │  retry+timeout  │      
│ load)  │   │            │   │  cheap+strong│  │                 │      
└────────┘   └──────┬─────┘   └──────┬──────┘   └─────────────────┘      
                    │                │                                    
              ┌─────▼────────────────▼──────┐                            
              │  Postgres 16 + pgvector     │                            
              │  users, runs, tool_calls,   │                            
              │  embeddings                  │                            
              └─────────────────────────────┘                            
```

External services: weather API, flights API, FX API, LangSmith (tracing), Discord webhook (default channel).

---

## Project Structure (target)

```
project4_smart_travel_planner/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, lifespan, CORS, router include
│   │   ├── core/
│   │   │   ├── settings.py          # pydantic-settings — single source of truth
│   │   │   ├── logging.py           # structlog/JSON setup
│   │   │   ├── security.py          # bcrypt + JWT helpers
│   │   │   └── exceptions.py        # AppError hierarchy
│   │   ├── db/
│   │   │   ├── session.py           # async engine + AsyncSession factory
│   │   │   ├── base.py              # Declarative Base
│   │   │   └── models/              # User, AgentRun, ToolCall, Embedding
│   │   ├── schemas/                 # Pydantic request/response
│   │   ├── routers/                 # auth, chat, runs, health
│   │   ├── services/                # business logic (auth, runs, tokens, webhook)
│   │   ├── deps/                    # FastAPI Depends() providers
│   │   ├── ml/
│   │   │   └── classifier_loader.py # loads joblib once via lifespan
│   │   ├── rag/
│   │   │   ├── loader.py
│   │   │   ├── chunker.py
│   │   │   ├── embedder.py          # async batch embeddings
│   │   │   └── store.py             # pgvector ops (async SQLAlchemy)
│   │   ├── agent/
│   │   │   ├── graph.py             # LangGraph state machine
│   │   │   ├── state.py             # AgentState TypedDict
│   │   │   ├── prompts.py           # system prompts (separate from user)
│   │   │   ├── llm_clients.py       # cheap + strong clients, cached
│   │   │   ├── security.py          # _sanitize_query, _sanitize_feature_string, suspicious-pattern logger
│   │   │   └── tools/
│   │   │       ├── base.py          # BaseTool ABC — every tool MUST implement run()
│   │   │       ├── retrieve_destinations.py
│   │   │       ├── classify_style.py
│   │   │       └── live_conditions.py
│   │   └── webhook/
│   │       ├── publisher.py         # tenacity retry + timeout
│   │       └── adapters.py          # Discord (default), Slack
│   ├── alembic/                     # migrations (incl. CREATE EXTENSION vector)
│   ├── tests/
│   │   ├── unit/                    # tools, schemas, services
│   │   ├── integration/             # routers, db
│   │   └── e2e/                     # full agent run with mocked externals
│   ├── pyproject.toml
│   └── Dockerfile
│
├── ml/                              # ML lifecycle — training & exploration
│   ├── data/
│   │   ├── raw/                     # original destinations dataset (read-only)
│   │   ├── processed/
│   │   └── labeling/
│   │       └── labeling_rules.md    # MANDATORY — explains every label
│   ├── notebooks/                   # exploration only, logic exported to src/
│   ├── src/
│   │   ├── data_loader.py
│   │   ├── feature_pipeline.py      # sklearn Pipeline (preprocessing inside)
│   │   ├── train.py                 # 3-classifier comparison + CV
│   │   ├── tune.py                  # GridSearchCV on the winner
│   │   ├── evaluate.py              # per-class metrics, baseline comparison
│   │   └── persist_model.py         # save winner_v<n>.joblib + results.csv row
│   ├── results/results.csv          # one row per experiment
│   ├── models/                      # winner artifacts (committed via LFS or .gitignore w/ link)
│   ├── tests/
│   └── pyproject.toml               # separate env for training-only deps
│
├── rag/
│   ├── data/
│   │   ├── raw/                     # scraped Wikivoyage / blog text
│   │   └── knowledge/               # cleaned, ingestion-ready
│   └── scripts/ingest.py            # CLI: read knowledge/ → chunk → embed → upsert
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api/client.js            # axios instance + JWT interceptor
│   │   ├── auth/                    # SignIn, SignUp pages + AuthContext
│   │   ├── chat/                    # ChatPanel, MessageList, Composer
│   │   ├── runs/                    # RunDetail (which tools fired)
│   │   └── components/              # shared primitives
│   ├── vite.config.js
│   ├── nginx.conf                   # production proxy
│   ├── package.json
│   └── Dockerfile
│
├── infra/
│   ├── postgres/init-pgvector.sql   # CREATE EXTENSION (compose `initdb` hook)
│   └── github-actions/ci.yml        # pytest on push
│
├── docker-compose.yaml              # extends starter w/ backend, frontend
├── .env.example                     # every required variable, fake values
├── .gitignore
├── .dockerignore
├── .pre-commit-config.yaml
├── README.md                         # architecture, setup, run, env, deploy
└── plan.md                            # mirror of this strategic plan, in the repo
```

---

## Stages

Each stage ends with a **Validation** gate. We do not advance without passing.

---

### Stage 0 — Scaffolding & Blueprinting

**Goal:** create every file & folder above. Files contain only:
- Module-level docstring describing intended functionality, key classes/functions, and how the module interacts with neighbours.
- Where useful, named placeholders (e.g. `def signup(...) -> ...:  # implemented in Stage 2`) so imports resolve later.
- No business logic.

**Deliverables:**
- Full directory tree (matches the target above)
- `.env.example`, `.gitignore`, `.dockerignore`, `.pre-commit-config.yaml`, `pyproject.toml` files (skeletons with sections present, dependencies pinned in Stage 1)
- `plan.md` copied into repo root for reviewer-visible context

**Validation:**
- `tree -L 3` matches the agreed structure
- `python -c "import ast, pathlib; [ast.parse(p.read_text()) for p in pathlib.Path('.').rglob('*.py')]"` parses every file
- Every Python file has a module docstring (grep check)
- User reviews & approves the structure before any Stage 1 code is written

---

### Stage 1 — Foundation (config, logging, app skeleton, tooling)

**Scope:**
- `core/settings.py`: pydantic-settings `Settings` class loading every env var (typed, validated at startup); singleton via `@lru_cache`
- `core/logging.py`: JSON-structured logger setup; module-level `logger = logging.getLogger(__name__)` used everywhere
- `core/exceptions.py`: `AppError`, `AuthError`, `ToolError`, `WebhookDeliveryError`, etc.
- `app/main.py`: FastAPI app, `lifespan` context manager (placeholders for db engine, ML model, embedding client, vector-store handle, LLM clients), CORS, router includes, `/health`
- `pyproject.toml` (backend): pinned exact versions — fastapi, uvicorn, pydantic, pydantic-settings, sqlalchemy[asyncio], asyncpg, alembic, pgvector, langgraph, langchain-core, the chosen LLM SDK, httpx, tenacity, bcrypt, pyjwt, structlog, scikit-learn, joblib, pytest, pytest-asyncio, httpx, mypy, black, isort, flake8
- `.pre-commit-config.yaml`: black → isort → flake8 → mypy → pytest → gitleaks
- `.env.example`: every required key with placeholder
- `Dockerfile` (backend): slim Python, multi-stage, non-root user
- `docker-compose.yaml`: extends provided starter — adds `backend` service (depends_on db, healthcheck), `frontend` service stub, named volumes already in starter

**Validation:**
- `uv sync` succeeds in `backend/`
- `uv run pre-commit run --all-files` passes
- `docker compose up -d db backend` → `curl localhost:8000/health` returns `{"status":"ok"}`
- `pytest tests/` runs (zero or one trivial test, all green)
- `mypy --strict app/` passes

---

### Stage 2 — Persistence & Auth

**Scope:**
- Async SQLAlchemy engine + `AsyncSession` factory; bound to lifespan
- Models: `User(id, email, password_hash, created_at)`, `AgentRun(id, user_id, question, final_answer, total_tokens, total_cost, started_at, finished_at)`, `ToolCall(id, run_id, tool_name, args_json, result_json, tokens, latency_ms, error, created_at)`, `Embedding(id, source, chunk_index, text, vector(N))` (pgvector)
- Alembic init; first migration creates `vector` extension and all tables
- `services/auth_service.py`: bcrypt hashing, signup, login, JWT issue/verify
- `routers/auth.py`: `POST /auth/signup`, `POST /auth/login` (returns access token)
- `deps/auth.py`: `current_user` Depends — decodes JWT, fetches user, raises `HTTPException(401)` on invalid
- `deps/db.py`: `get_session` Depends yields `AsyncSession`

**Validation:**
- Alembic upgrade/downgrade clean roundtrip
- pytest: schema rejects malformed signup, password hashed (never stored plaintext, never logged), login wrong password → 401, current_user dep recovers user
- Coverage on `services/auth_service.py` ≥ 95% (critical path)

---

### Stage 3 — ML Classifier Lifecycle

This is the dedicated ML stage and gets the most rigour.

**Sub-stages:**

3.1. **Dataset construction (100–200 destinations, 6 labels)**
- Source destinations from a public list (e.g., curated Wikivoyage list, Numbeo cost data) — read-only in `ml/data/raw/`
- Features: `country`, `region`, `avg_temp_c`, `cost_per_day_usd`, `safety_index`, `language_difficulty`, `activity_density_index`, `nightlife_score`, `cultural_sites_count`, `nature_score`, etc. (set finalized during 3.2)
- Labels: `Adventure | Relaxation | Culture | Budget | Luxury | Family`
- **`ml/data/labeling/labeling_rules.md`** — for each label, a written rule (e.g. "Adventure = activity_density ≥ 7 AND nature_score ≥ 6 AND cost ≤ \$100/day"). Mandatory deliverable per the brief.

3.2. **Feature pipeline**
- `ml/src/feature_pipeline.py`: sklearn `Pipeline` with `ColumnTransformer` doing imputation + scaling + one-hot encoding inside the pipeline (never pre-transformed) — protects against leakage
- Justification doc: every feature kept and every dropped feature reasoned

3.3. **Model comparison**
- 3 classifiers: Logistic Regression (one-vs-rest, with `class_weight="balanced"`), Random Forest (with `class_weight="balanced"`), Gradient Boosting (HistGradientBoostingClassifier or XGBoost)
- StratifiedKFold (k=5), `random_state=42` everywhere
- Metrics: accuracy AND macro-F1 — mean ± std across folds, plus per-class precision/recall/F1
- Baseline: `DummyClassifier(strategy="stratified")` for comparison
- Class imbalance: report counts, choose between `class_weight="balanced"` vs SMOTE (justify pick), report per-class metrics

3.4. **Tuning**
- GridSearchCV on the winner with stratified CV; describe search space & why
- Final model retrained on full training split, evaluated on held-out test set

3.5. **Persistence**
- Save as `ml/models/travel_style_classifier_v1.joblib`
- Append row to `ml/results/results.csv` with: timestamp, model, params, accuracy_mean, accuracy_std, f1_macro_mean, f1_macro_std, per-class metrics, dataset hash
- Pin `random_state` in every stochastic call; record dataset hash for reproducibility

**Validation:**
- `pytest ml/tests/` passes — pipeline transforms a sample, classifier predicts a sample, results.csv has at least one row, joblib loads and predicts deterministically
- Reproducibility: re-run training → identical metrics (within float tolerance)
- README of `ml/` includes: dataset rules, feature justifications, model comparison table, baseline comparison, chosen model + tuning rationale

---

### Stage 4 — RAG Pipeline

**Scope:**
- Source 10–15 destinations × 2 docs each (Wikivoyage stable export + 1 secondary) into `rag/data/raw/`
- Loader (text/markdown) → chunker → embedder → store
- Chunker: sentence-aware, default 500 chars / 50 overlap (justified in `rag/README.md`)
- Embedder: async, batched, calls **local Ollama** (`POST /api/embeddings` with model `nomic-embed-text`, 768-dim) via `httpx.AsyncClient`; client cached via `lru_cache`; tenacity retries with backoff on connection errors; embedding dim asserted equal to `Settings.embed_dim`
- Store (`backend/app/rag/store.py`): pgvector cosine, deterministic IDs `{source}_{chunk_index}` for upsert idempotency, async SQLAlchemy
- CLI: `rag/scripts/ingest.py` — reads knowledge/, calls the pipeline
- `rag/README.md`: chunk-size rationale, overlap rationale, retrieval-strategy rationale (top-k, similarity threshold), 3+ hand-written queries with retrieved-chunk screenshots demonstrating quality

**Validation:**
- pytest: chunker boundary correctness, embedder batch shape, store upsert idempotency, similarity search returns relevant chunks for canned queries
- Re-running ingestion produces same vector count (no duplicates)

> **Note:** All ML and RAG narrative (labeling rules, feature justifications, model comparison table, chunking rationale, retrieval strategy) is consolidated into the root `README.md`. No separate `ml/README.md` or `rag/README.md`. The `labeling_rules.md` data file remains because it's a dataset artifact, not a duplicate readme.

---

### Stage 5 — Agent (LangGraph + 3 Tools + Two Models)

**Scope:**
- `agent/state.py`: `AgentState` TypedDict (messages, intent, retrieved, classification, live_conditions, plan, tokens_cheap, tokens_strong)
- `agent/llm_clients.py`: two cached **Gemini** clients — `cheap = gemini-2.5-flash` (extraction, query rewriting, routing, tool-arg generation) and `strong = gemini-2.5-pro` (final synthesis only). Both async, with timeouts, `max_output_tokens`, structured-output schemas where applicable, and tenacity retries on `RetryableError`/timeouts. Token usage extracted from response metadata and persisted per `tool_call`.
- `agent/prompts.py`: separate system prompts (role + format + invariants) and user-prompt templates. User input wrapped in `<user_input>` tags, sanitized.
- `agent/tools/`:
  - `retrieve_destinations.py` — input: `RetrieveQuery` Pydantic; output: `RetrieveResult`. Calls embedder + vector store.
  - `classify_style.py` — input: `ClassifyInput` (the destination feature dict — extracted by cheap model from RAG result); output: `ClassifyResult` (label + probability). Loads joblib via lifespan singleton.
  - `live_conditions.py` — input: `LiveConditionsQuery` (city, dates, currency_pair); output: `LiveConditions` (weather, sample flight prices, FX rate). Three sub-clients: Open-Meteo (weather, no key), exchangerate.host (FX, no key), Amadeus (flights, key-gated with graceful degradation — returns `{available: false, reason: "..."}` when key absent or quota exhausted). All via shared `httpx.AsyncClient` with timeouts, tenacity, TTL cache (cachetools, 10 min for weather/FX, 1 hour for flights).
- **`tools/base.py`** — `class BaseTool(ABC)` defines:
  - `name: str` (class attribute, used for the allowlist)
  - `input_schema: type[BaseModel]` (class attribute, the Pydantic input model)
  - `output_schema: type[BaseModel]` (class attribute, the Pydantic output model)
  - `async def run(self, args: BaseModel) -> BaseModel` (abstract — subclasses implement)
  - Concrete helper `async def safe_run(self, raw_args: dict) -> ToolResult` — validates `raw_args` against `input_schema`, calls `run()`, wraps exceptions as structured `ToolResult{ok: false, error: ...}`, never raises into the agent loop. This is the only entry point the LangGraph node calls.
- All three concrete tools subclass `BaseTool`. The agent registry is a dict `{tool.name: tool}` built from the subclass list — adding a tool requires zero changes elsewhere.
- Each tool: pydantic input validated → on validation failure structured error returned to LLM (NOT raised) → LLM retries with corrected args. Allowlist enforced; agent rejects any tool name not in the registry.
- Prompts go through the §19 guardrails (sanitize, `<user_input>` tags, `max_output_tokens`, suspicious-pattern logging).
- `agent/graph.py`: LangGraph state machine — Plan → Tool-Loop (cheap routes & extracts args) → Synthesis (strong model). Token & cost logged per step into `tool_calls` table.
- LangSmith tracing wired (env-gated); `LANGCHAIN_TRACING_V2=true` enables it.

**Validation:**
- pytest: each tool tested in isolation with a fake LLM and stubbed external calls; pydantic schemas tested with valid AND invalid inputs; one e2e test exercises the full graph with all three tools mocked
- Manual: 1 real query end-to-end, screenshot of LangSmith trace
- Cost report: token usage logged for one full query, written into README

---

### Stage 6 — Chat API + History

**Scope:**
- `routers/chat.py`: `POST /chat` (auth-protected, body = `ChatRequest{question, webhook_url?}`) — kicks off agent run, persists `AgentRun` + `ToolCall` rows, returns `ChatResponse{run_id, answer, tools_fired}`
- `routers/runs.py`: `GET /runs` (list user's runs), `GET /runs/{id}` (full trace incl. tool calls)
- Authorization: `current_user` Depends; routes filter by `user_id`. User A cannot read User B's runs.
- Webhook fired in background after response is built — failure does NOT break response.

**Validation:**
- pytest: cross-user isolation (A's token cannot read B's runs → 404), persistence verified, webhook fire-and-forget proven
- Coverage on routers ≥ 90%

---

### Stage 7 — React Frontend

**Scope:**
- Vite + React + TypeScript, axios client w/ JWT interceptor
- Pages: SignIn, SignUp, Chat (chat-style transcript with tool-fire badges), RunDetail (timeline of tools, args, returns, latency)
- Auth context, protected routes
- Streaming optional — start with single-shot

**Validation:**
- Manual: start dev server, sign up, ask a question, see tools fire, view run detail
- Lint/build clean

---

### Stage 8 — Webhook Delivery

**Scope:**
- `webhook/publisher.py`: async, tenacity retry (1 retry, exponential backoff), 5s timeout; on final failure logs structured error and persists `webhook_delivery_status` on the run
- `webhook/adapters.py`: Discord adapter (default), Slack adapter
- Background task scheduling via FastAPI `BackgroundTasks`

**Validation:**
- pytest: stub receiver server; success path; transient-failure-then-success; permanent-failure logs error and run completes anyway

---

### Stage 9 — Containerization & Deployment

**Scope:**
- Backend Dockerfile (multi-stage, slim, non-root)
- Frontend Dockerfile (build → nginx serve, with nginx.conf proxying /api → backend)
- `docker-compose.yaml` final form: db (pgvector) + **ollama** + backend + frontend + pgadmin (optional). Healthchecks. Named volumes for db data AND ollama models (so re-pulling on restart isn't required).
- `infra/postgres/init-pgvector.sql` runs `CREATE EXTENSION vector;` on first init
- `infra/ollama/pull-models.sh` (one-shot init): waits for ollama to be ready, then `ollama pull nomic-embed-text`
- Environment-driven `CORS_ORIGINS`

**Validation:**
- `docker compose down -v && docker compose up --build` cold-start works
- Sign up, ask a question, restart stack, verify history & embeddings persist
- All inter-service calls use service names (no hardcoded IPs)

---

### Stage 10 — Documentation, CI & Demo

**Scope:**
- Top-level `README.md` per CLAUDE §21:
  - Project description & architecture diagram
  - Prerequisites (Docker, uv, Node)
  - Setup (clone, copy `.env.example` → `.env`, fill keys, `docker compose up`)
  - Environment variables (every var, purpose, required/optional)
  - Project structure (mini tree)
  - **Required artifacts:** dataset labeling rules link, chunking/retrieval rationale link, model comparison table, per-query cost breakdown, LangSmith trace screenshot, list of optional extensions completed
  - Deployment notes (Railway/Fly/Render for backend, Vercel for frontend)
- `.github/workflows/ci.yml`: pytest, mypy, lint on every push
- 3-minute demo video script

**Validation:**
- Hand README to a fresh reader → they can clone & run with no questions
- CI green on first push
- README pre-review checklist (CLAUDE §24) all items ticked

---

---

## Optional / Stretch Stages (do not start until Stages 0–10 are end-to-end green)

The brief explicitly lists optional extensions — "pick what interests you. Don't start any of these until your required nine work end to end." These are scoped here so we can pick them up without re-planning, but we will not begin them until the user signs off after Stage 10.

### Stage O1 — Experiment Tracking with MLflow or Weights & Biases
- Replace `results.csv` with proper experiment tracking: every run, every artifact, every metric, every dataset hash.
- Add a tracking-server service (MLflow) or a W&B project link.
- Screenshot of the dashboard goes into the README.

### Stage O2 — Structured Logging Sink (Seq / Grafana Loki / Better Stack)
- Replace stdlib JSON logger with structlog + a sink shipper.
- Every agent run, every tool call, every failure is reconstructable from logs alone.
- Correlation IDs propagated via FastAPI middleware.

### Stage O3 — Secrets Management (HashiCorp Vault / Doppler / Infisical)
- Move keys out of `.env` into a managed store; inject at runtime via the chosen provider's SDK.
- `Settings` reads from the manager when an env var marks the lookup mode (e.g. `SECRETS_BACKEND=vault`).

### Stage O4 — Production Deployment
- Backend on Railway / Fly.io / Render.
- Database on Supabase (pgvector supported) or Neon.
- Frontend on Vercel.
- Live URLs published in the README.

### Stage O5 — Push the Agent Itself
- Human-in-the-loop approval before the webhook fires (UI confirmation step).
- "Compare two destinations" mode (parallel sub-graphs).
- Planner-then-executor agent vs. ReAct comparison, with a written reflection in the README.
- Cache layer for live APIs beyond the per-process TTL — e.g. shared Redis cache for multi-replica deployments.

Each optional stage gets its own validation gate and PR. None blocks any other.

---

## Critical Files Summary

| File | Purpose | Stage introduced |
|------|---------|------------------|
| `backend/app/core/settings.py` | Single config source | 1 |
| `backend/app/main.py` | App + lifespan singletons | 1 |
| `backend/app/db/models/*.py` | SQLAlchemy schema | 2 |
| `backend/app/agent/graph.py` | LangGraph state machine | 5 |
| `backend/app/agent/tools/base.py` | `BaseTool` ABC w/ `run()` contract + `safe_run()` wrapper | 5 |
| `backend/app/agent/tools/{retrieve,classify,live}*.py` | Concrete tools subclassing `BaseTool` | 5 |
| `backend/app/agent/security.py` | `_sanitize_query`, `_sanitize_feature_string`, suspicious-pattern logger | 5 |
| `ml/src/train.py` | 3-classifier comparison + CV | 3 |
| `ml/data/labeling/labeling_rules.md` | Dataset labeling rules (mandatory) | 3 |
| `rag/scripts/ingest.py` | Knowledge → pgvector | 4 |
| `rag/README.md` | Chunking & retrieval rationale | 4 |
| `frontend/src/App.jsx` | Chat + run-detail UI | 7 |
| `docker-compose.yaml` | Whole-stack orchestration | 9 |
| `README.md` | Project documentation | 10 |

---

## Confirmed Technology Decisions

| Decision | Choice | Notes |
|----------|--------|-------|
| LLM (cheap) | Google Gemini 2.5 Flash (or Flash-Lite) | `google-generativeai` SDK, async via SDK's `*_async` methods or run-in-executor; per CLAUDE.md §18 |
| LLM (strong) | Google Gemini 2.5 Pro | Same SDK, used only for final synthesis in Stage 5 |
| Embeddings | **Ollama local** (`nomic-embed-text`, 768-dim) | Runs as a docker-compose service; backend talks to it via `http://ollama:11434/api/embeddings`; async httpx; embeddings never leave the box |
| Vector store | Postgres + pgvector | `vector(768)` column matched to chosen Ollama model |
| Frontend | **Vite + React + TypeScript** | Typed boundaries mirror backend Pydantic discipline |
| Live weather | Open-Meteo (no key, free) | Required |
| Live FX | exchangerate.host (no key, free) | Required |
| Live flights | Amadeus self-service sandbox | Required when `AMADEUS_API_KEY` is set; **gracefully degrades** to a structured "flights unavailable" response if unset or quota exhausted — the agent must reason about missing data, not crash |
| Webhook channel | Discord (default) | Slack adapter included as second adapter for completeness |
| Auth | JWT access tokens, bcrypt hashing | Refresh tokens deferred to optional |
| Agent framework | LangGraph | State machine clarity for tool-loop + synthesis nodes |
| Tracing | LangSmith (env-gated via `LANGCHAIN_TRACING_V2`) | Free tier sufficient |

**Implications for the stack:**
- `docker-compose.yaml` adds an `ollama` service alongside db/backend/frontend; named volume for pulled models so they survive restarts.
- A bootstrap step pulls `nomic-embed-text` on first launch (one-shot init container or backend lifespan check).
- Embedding dimension is hard-coded `EMBED_DIM=768` in settings, matching the pgvector column. Switching models requires a migration — documented in the root README.
- The cost-breakdown in the README only covers Gemini calls (embeddings are free locally).

---

## Caching Strategy (explicit, per the brief's "document where you cached and why")

The project brief mandates `lru_cache` for deterministic+expensive loads and a TTL cache for repeated tool calls. Both are sanctioned and used. Wrong caching is worse than no caching, so every cache below has an explicit invalidation answer.

| Subject | Mechanism | Why | Invalidation |
|---------|-----------|-----|--------------|
| `Settings` (pydantic-settings) | `@lru_cache(maxsize=1)` | Reads env once at startup | Process restart only — settings are immutable post-boot |
| Gemini cheap/strong client | `@lru_cache(maxsize=1)` | Client construction is expensive (HTTP session, retries, auth) | Process restart |
| Ollama embedding client (`httpx.AsyncClient`) | `@lru_cache(maxsize=1)` | Reuse connection pool | Process restart; closed in lifespan shutdown |
| ML classifier joblib | Loaded once in **lifespan**, attached to `app.state.classifier` | One-time deserialization cost; loading per request is the brief's named anti-pattern | Process restart only — to ship a new model, redeploy |
| Open-Meteo weather response | `cachetools.TTLCache(maxsize=256, ttl=600)` | "Same city in 10 minutes is the same answer" — quoted directly from the brief | TTL expiry (10 min); cache key = `(lat, lon, date)` |
| exchangerate.host FX response | `cachetools.TTLCache(maxsize=128, ttl=3600)` | Rates barely move in an hour | TTL (1 hour); cache key = `(base, quote, date)` |
| Amadeus flight quote | `cachetools.TTLCache(maxsize=128, ttl=3600)` | Same query within an hour returns close enough quotes | TTL (1 hour); cache key = `(origin, destination, date)` |
| RAG search result | **NOT cached** | Different queries embed differently; an LRU on `query_text` pollutes with false hits | n/a — and we explicitly say so in the README, since "caching the wrong thing is worse than not caching" |
| LLM call results | **NOT cached** | Synthesis depends on full conversation state; caching introduces stale plans | n/a |

**Rule applied:** caches live in **one** place per subject (in the module that owns the resource), not scattered. Invalidation is documented next to each cache definition with a one-line comment naming the trigger.

---

## Prompt-Injection Guardrails (per CLAUDE.md §19)

User input flows into Gemini prompts. Every Stage-5 tool must enforce:

1. **Sanitize before format()** — `_sanitize_query()` in `agent/security.py` normalizes whitespace, strips control chars, truncates to a max length, and removes prompt-leakage triggers (e.g. lines starting with `system:`, `assistant:`, `###`).
2. **Delimited user content** — every prompt template wraps user-supplied text in `<user_input>...</user_input>` tags. No raw user text adjacent to instructions.
3. **Sanitize LLM string outputs before re-use** — `_sanitize_feature_string()` runs on any string from a cheap-model output that flows back into another prompt or a tool argument (e.g. extracted destination name → next tool).
4. **`max_output_tokens` on every Gemini call** — both clients ship with sane caps to block exfiltration.
5. **No `eval` / `exec` on LLM output** — ever. Tool args are JSON-parsed and Pydantic-validated; if parsing fails, the structured error is sent back to the LLM for retry.
6. **Suspicious-pattern logging** — patterns (`ignore previous`, `you are now`, `system prompt`, `\\n\\nHuman:`, etc.) are logged at WARNING but not rejected. FastAPI rate-limiting handles abuse at the request layer.
7. **Pydantic is the fence** — every tool's input is a Pydantic model; structurally invalid args never reach the implementation. Pydantic validation errors return as structured tool errors to the LLM, never as exceptions to the user.
8. **Tool allowlist** — agent rejects any tool name outside `{retrieve_destinations, classify_style, live_conditions}`, even if the LLM hallucinates one.

---

## Execution Protocol

1. User reviews & approves this plan and the scaffolded directory.
2. After approval, we proceed Stage 0 → Stage 10 sequentially.
3. After each stage, run all relevant tests and stop. Do not begin the next stage until the validation gate passes and the user signs off.
4. Each stage will be merged via a separate PR (per CLAUDE §7: one concern per PR, ≤ 400 lines). Branch naming follows §5.

---
