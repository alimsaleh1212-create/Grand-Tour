# Smart Travel Planner

> Status: scaffolded (Stage 0). Implementation rolls out stage-by-stage per `plan.md`.

A travel-planning agent that turns a free-form trip request ("two weeks in July, ~$1500, warm + hiking, not too touristy") into a real itinerary. The agent retrieves destination knowledge over a RAG store, classifies destinations by travel style with a trained ML model, fetches live weather/FX/flight data, synthesises a plan with a strong LLM, and delivers it to a Discord webhook.

## Architecture

```
React + Vite (TS)  ──HTTP+JWT──▶  FastAPI (async, DI, lifespan singletons)
                                     │
                  ┌──────────────────┼─────────────────────┐
                  ▼                  ▼                     ▼
              ML joblib        RAG (pgvector)      Agent (LangGraph)
              (1× load)        + Ollama embeds    cheap+strong Gemini
                                                  3 tools w/ Pydantic
                                                  + injection guards
                  └────────┬──────────┬───────────────────┘
                           ▼          ▼
                       Postgres 16 + pgvector
                       (users, runs, tool_calls, embeddings)
                                                  │
                                                  ▼
                                          Discord webhook
```

## Prerequisites

- Docker + Docker Compose
- `uv` (Python toolchain) — for local backend/ML development outside Docker
- Node 20+ + pnpm — for local frontend development outside Docker

## Setup

```bash
cp .env.example .env       # then fill in GOOGLE_API_KEY at minimum
docker compose up --build  # cold-starts db, ollama, backend, frontend
```

The backend serves on `http://localhost:8000`, the frontend on `http://localhost:5173`, pgAdmin (optional) on `http://localhost:8080`.

## Environment Variables

Every variable, its purpose, and whether it's required is documented in [`.env.example`](.env.example). At minimum:

| Variable | Required | Purpose |
|----------|----------|---------|
| `GOOGLE_API_KEY` | ✅ | Gemini API key for cheap + strong models |
| `JWT_SECRET` | ✅ | HS256 signing key for access tokens |
| `POSTGRES_*` | ✅ | Database credentials |
| `AMADEUS_API_KEY` | ⚪ optional | Flights tool degrades gracefully when absent |
| `LANGCHAIN_API_KEY` | ⚪ optional | LangSmith tracing |
| `DISCORD_WEBHOOK_URL` | ⚪ optional | Webhook delivery target |

## Project Structure

```
backend/   FastAPI service (async, DI, lifespan singletons)
ml/        Training package — dataset, sklearn pipeline, results.csv
rag/       Knowledge sources + ingestion CLI (chunk, embed, upsert)
frontend/  Vite + React + TypeScript SPA
infra/     Postgres init SQL, Ollama bootstrap, GitHub Actions CI
```

## Documentation Sections — to be completed per stage

- **Dataset labeling rules** — `ml/data/labeling/labeling_rules.md` (Stage 3)
- **Model comparison table** — appended below by Stage 3
- **Chunking & retrieval rationale** — appended below by Stage 4
- **Per-query cost breakdown** — appended below by Stage 5
- **LangSmith trace screenshot** — added in Stage 5
- **Architecture diagram** — added in Stage 10
- **Deployment URLs** — populated if Stage O4 (optional) is completed

## Development Workflow

See `plan.md` for the stage-by-stage implementation plan. Each stage is one PR (≤400 lines, single concern, branch named `<type>/<short-description>`).

## License

Educational use — AIE Bootcamp Week 4 project.
