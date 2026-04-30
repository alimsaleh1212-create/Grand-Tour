# Grand Tour — Smart Travel Planner

An AI-powered travel planning agent that turns a free-form trip request into a personalised itinerary. The agent retrieves destination knowledge from a pgvector RAG store, classifies destinations by travel style with a trained ML model, fetches live weather / FX / flight data, and synthesises a full travel plan using Gemini. Results stream progressively to the browser via Server-Sent Events so the user sees each tool result the moment it's ready.

---

## Architecture

```
React + Vite (TS)  ──HTTP+JWT──▶  FastAPI (async, DI, lifespan singletons)
       ▲                                │
  SSE stream                ┌──────────┼─────────────────────┐
  (progressive)             ▼          ▼                     ▼
                       ML joblib   RAG (pgvector)     LangGraph Agent
                       1× load     Gemini embeds      cheap+strong Gemini
                                   768-dim cosine     3 tools + injection guards
                            └──────────┬───────────────────┘
                                       ▼
                              Postgres 16 + pgvector
                           (users · runs · tool_calls · embeddings · bookings)
                                       │
                                       ▼
                              Discord/Slack webhook
```

**Services in Docker Compose:**

| Service    | Image / Build       | Port   | Purpose                                   |
|------------|---------------------|--------|-------------------------------------------|
| `db`       | pgvector/pgvector:pg16 | 5432 | Postgres + vector extension               |
| `backend`  | `./backend`         | 8000   | FastAPI — agent, auth, chat, runs, bookings |
| `frontend` | `./frontend`        | 3000   | React SPA served by nginx                 |
| `pgadmin`  | dpage/pgadmin4      | 8080   | Optional DB explorer                      |

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) + Docker Compose v2
- [`uv`](https://docs.astral.sh/uv/) — for local backend / ML development outside Docker
- Node 20+ — for local frontend development outside Docker
- A **Google API Key** with the Gemini API enabled (free tier works)

---

## Setup

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd project4_smart_travel_planner

# 2. Copy the example env file and fill in your secrets
cp .env.example .env
#   Required: GOOGLE_API_KEY, JWT_SECRET, POSTGRES_PASSWORD
#   Optional: AMADEUS_API_KEY, LANGCHAIN_API_KEY, DISCORD_WEBHOOK_URL

# 3. Start the full stack (builds images on first run — ~3 min)
docker compose up --build -d

# 4. (First run only) Ingest the knowledge base into pgvector
docker compose exec backend python -m rag.scripts.ingest

# 5. Open the app
open http://localhost:3000
```

The backend API docs are at `http://localhost:8000/docs` (dev mode only).

---

## How to Run (local development)

**Backend:**
```bash
cd backend
cp ../.env.example ../.env   # fill secrets
uv sync                       # install deps into .venv
uv run alembic upgrade head   # apply migrations
uv run uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev   # starts Vite dev server at http://localhost:5173
```

**ML training (optional — model already committed):**
```bash
cd ml
uv sync
uv run python src/train.py
```

**RAG ingestion (requires running Postgres):**
```bash
cd backend
uv run python -m rag.scripts.ingest
```

---

## Environment Variables

All secrets and config live in one `.env` file (see `.env.example`). The backend enforces `extra="forbid"` — a typo crashes at startup, not silently later.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `GOOGLE_API_KEY` | ✅ | — | Gemini API (cheap + strong models + embeddings) |
| `JWT_SECRET` | ✅ | — | HS256 signing key (min 32 chars) |
| `POSTGRES_PASSWORD` | ✅ | — | Postgres app user password |
| `POSTGRES_HOST` | | `db` | Service name inside Docker network |
| `POSTGRES_PORT` | | `5432` | |
| `POSTGRES_USER` | | `travel` | |
| `POSTGRES_DB` | | `travel` | |
| `GEMINI_CHEAP_MODEL` | | `gemini-2.5-flash` | Extraction, routing, tool-arg generation |
| `GEMINI_STRONG_MODEL` | | `gemini-2.5-pro` | Final plan synthesis (fires once per request) |
| `GEMINI_EMBED_MODEL` | | `models/gemini-embedding-001` | 768-dim embeddings |
| `ML_MODEL_PATH` | | `../ml/models/travel_style_classifier_v1.joblib` | Trained sklearn pipeline |
| `AMADEUS_API_KEY` | ⚪ | — | Live flight search (degrades gracefully if absent) |
| `LANGCHAIN_API_KEY` | ⚪ | — | LangSmith tracing |
| `DISCORD_WEBHOOK_URL` | ⚪ | — | Default webhook delivery target |
| `CORS_ORIGINS` | | `["http://localhost:5173"]` | Allowed frontend origins |
| `LOG_LEVEL` | | `INFO` | |
| `APP_ENV` | | `development` | Set to `production` to hide /docs |

---

## Project Structure

```
backend/
  app/
    agent/          LangGraph agent: graph, tools, prompts, security, LLM clients
    core/           Settings, logging, security (JWT), exceptions
    db/             SQLAlchemy models, session factory, Alembic base
    deps/           FastAPI Depends() providers (auth, db, agent)
    ml/             Classifier loader
    rag/            Chunker, embedder, vector store (pgvector)
    routers/        auth, chat (SSE), runs, bookings, health
    schemas/        Pydantic request/response models
    services/       run_service (create, append tool calls, finalise)
    webhook/        Publisher + Discord/Slack adapters
  alembic/          DB migrations
  tests/unit/       77 offline unit tests
ml/
  data/
    raw/            destinations_raw.csv (160 rows, 6 labels — read-only)
    processed/      Cleaned dataset
    labeling/       labeling_rules.md (written before training)
  src/              feature_pipeline.py, train.py, evaluate.py
  models/           travel_style_classifier_v1.joblib
  results/          results.csv (one row per experiment)
rag/
  data/knowledge/   12 Markdown destination files (Wikivoyage-style)
  scripts/          ingest.py — offline batch chunker + embedder + upsert
frontend/
  src/
    api/            client.ts — axios + streamChat() SSE helper
    auth/           AuthContext, SignIn, SignUp
    chat/           ChatPanel, Composer, TravelPlanCards, BookingModal, HistorySidebar
    components/     NavBar, Spinner, ToolBadge
    runs/           RunDetail
infra/
  github-actions/   ci.yml
  postgres/         init-pgvector.sql
```

---

## ML Narrative

### Labeling Rules

Labels were defined in `ml/data/labeling/labeling_rules.md` **before** any model was trained. Six labels: Adventure, Relaxation, Culture, Budget, Luxury, Family — each with explicit decision rules based on observable destination features (not intuition). Dataset: 160 destinations, balanced with `class_weight="balanced"`.

### Feature Justifications

All 13 features are present in public destination data and directly causal for travel-style preference:

| Feature | Why kept |
|---|---|
| `avg_temp_c` | Temperature drives Beach/Relaxation vs. high-altitude Adventure |
| `cost_per_day_usd` | Primary signal for Budget vs. Luxury |
| `safety_index` | Family travellers require high safety; Adventure tolerates lower |
| `language_difficulty` | Culture travellers accept difficulty; Family prefers English-friendly |
| `activity_density` | Density of bookable activities is the strongest Adventure signal |
| `nightlife_score` | Relaxation destinations often pair beach + nightlife |
| `cultural_sites` | UNESCO count is the strongest Culture signal |
| `nature_score` | Wilderness access is key for Adventure |
| `beach_score` | Direct signal for Relaxation and Luxury resort destinations |
| `family_friendly` | Infrastructure for children (parks, healthcare, rides) |
| `infrastructure` | Luxury and Family require reliable services |
| `luxury_index` | Composite score of 5-star hotels + fine dining density |
| `region` (OHE) | Controls for continent-level confounders (e.g. SE Asia = Budget) |

**Dropped features:** `destination_name`, `country` (would cause leakage — labels were partially assigned from the name).

### Model Comparison (StratifiedKFold k=5, `random_state=42`)

| Model | Accuracy (mean ± std) | Macro-F1 (mean ± std) | Note |
|---|---|---|---|
| DummyClassifier (baseline) | 0.163 ± 0.046 | 0.159 ± 0.047 | Stratified random — the floor |
| LogisticRegression (L2) | 0.913 ± 0.036 | 0.911 ± 0.038 | Best cross-val; chosen for production |
| RandomForest (n=200) | 0.881 ± 0.054 | 0.878 ± 0.059 | Good but higher variance |
| HistGradientBoosting | 0.844 ± 0.020 | 0.845 ± 0.021 | Lower CV; overfits small dataset |
| **LogisticRegression (tuned)** | **0.938** | **0.961** | Final model after GridSearchCV (C=1.0) |

### Tuning Rationale

GridSearchCV over `C ∈ {0.01, 0.1, 1.0, 10}` and `solver ∈ {lbfgs, saga}`. Best: `C=1.0, solver=lbfgs`. The default C already prevented overfitting because the feature space is small and well-scaled. Class imbalance handled by `class_weight="balanced"` (preferred over SMOTE because the dataset is small and synthetic oversampling would copy identical feature vectors).

---

## RAG Narrative

### Chunking Strategy

Default: **500 chars / 50 char overlap, sentence-boundary-aware sliding window** (`backend/app/rag/chunker.py`). Each chunk includes a `source` and `chunk_index` for provenance. The 50-char overlap preserves sentence continuity across boundaries without duplicating large blocks.

Why 500/50: the 12 knowledge documents average 1,800 chars per H2 section. A 500-char window retrieves one logical section per chunk (practical information, top experiences, etc.) without splitting across unrelated topics. Overlap at 50 chars (one short sentence) is enough to recover truncated sentences without semantic duplication.

### Retrieval Strategy

- **Model:** `models/gemini-embedding-001` — 768-dimensional embeddings via Google's REST API
- **Distance:** cosine similarity (`<=>` operator in pgvector) — invariant to document length
- **Top-k:** 5 chunks per query — enough to cover 2–3 destination sections without flooding the synthesis prompt
- **Similarity threshold:** none enforced at retrieval; the synthesis prompt is instructed to discard irrelevant chunks
- **RAG results are not cached** — different queries embed differently; a cache would serve stale chunks for paraphrased questions

### Sample Queries and Retrieved Sections

| Query | Top retrieved section | Source file |
|---|---|---|
| "cost per day in Kyoto" | Practical Information (cost_per_day_usd: ¥8,000–15,000) | kyoto_wikivoyage.md |
| "best beach destination for relaxation" | Travel Style Profile (beach_score: 10/10) | maldives_wikivoyage.md |
| "adventure hiking in South America" | Top Experiences (Inca Trail, Patagonia routes) | peru_wikivoyage.md |

---

## Per-Request Cost Breakdown

Gemini pricing (as of 2026-04-30, pay-as-you-go):

| Call | Model | Approx tokens | Cost |
|---|---|---|---|
| Feature extraction (per destination chunk) | gemini-2.5-flash | ~800 in / 200 out | ~$0.0003 |
| Final synthesis | gemini-2.5-pro | ~3,000 in / 600 out | ~$0.015 |
| Embedding (5 chunks × 768-dim) | gemini-embedding-001 | ~200 tokens | ~$0.000025 |
| **Total per request** | | | **~$0.016** |

Costs are recorded per run in `agent_runs.cost_usd` (calculated in `services/run_service.py`).

---

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/signup` | — | Register new user |
| `POST` | `/auth/login` | — | Get JWT access token |
| `GET` | `/auth/me` | ✅ | Current user info |
| `POST` | `/chat/stream` | ✅ | SSE streaming agent run |
| `POST` | `/chat` | ✅ | Non-streaming agent run |
| `GET` | `/runs` | ✅ | List user's past runs |
| `GET` | `/runs/{id}` | ✅ | Run detail with tool-call timeline |
| `POST` | `/bookings` | ✅ | Confirm a demo flight booking |
| `GET` | `/bookings` | ✅ | List user's bookings |
| `GET` | `/bookings/{id}` | ✅ | One booking detail |
| `GET` | `/health` | — | Liveness probe |

Full interactive docs: `http://localhost:8000/docs`

---

## Deployment

**Render (recommended for demo):**

1. Create a Postgres instance on Render; copy the connection string.
2. Deploy `backend/` as a Web Service with the `Dockerfile`; set all env vars.
3. Deploy `frontend/` as a Static Site with build command `npm ci && npm run build` and publish dir `dist`; set `VITE_API_BASE_URL` to the backend URL.
4. Update `CORS_ORIGINS` in the backend env to include the frontend URL.

The `docker compose up` one-liner works on any machine with Docker installed.

---

## License

Educational use — AIE Bootcamp Week 4 project.
