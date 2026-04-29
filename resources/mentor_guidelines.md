# Mentor Guidelines — RAG Knowledge Assistant

A comprehensive guide to the project architecture, best practices, and design patterns for the RAG (Retrieval-Augmented Generation) Knowledge Assistant.

---

## Table of Contents

1. [Project Hierarchy](#project-hierarchy)
2. [Architectural Overview](#architectural-overview)
3. [RAG Pipeline Best Practices](#rag-pipeline-best-practices)
4. [FastAPI Best Practices](#fastapi-best-practices)
5. [RAG-FastAPI Communication Patterns](#rag-fastapi-communication-patterns)
6. [Coding Methodology](#coding-methodology)
7. [Common Patterns & Anti-Patterns](#common-patterns--anti-patterns)

---

## Project Hierarchy

```
rag-knowledge-assistant/
├── backend/                    # ⭐ Core backend logic
│   ├── __init__.py
│   ├── config.py              # Environment variables & configuration
│   ├── main.py                # FastAPI app initialization & CORS setup
│   ├── models.py              # Pydantic request/response schemas
│   ├── llm.py                 # LLM client wrapper (Gemini, OpenAI, Azure)
│   │
│   ├── prompts/               # System prompts for LLM
│   │   ├── plain_answer.py    # Direct LLM answers (no context)
│   │   └── grounded_answer.py # Context-injected answers (RAG mode)
│   │
│   ├── rag/                   # ⭐ RAG core modules
│   │   ├── loader.py          # File format parsing (PDF, CSV, JSON, Markdown)
│   │   ├── chunker.py         # Document splitting into overlapping chunks
│   │   ├── embedder.py        # Text-to-vector conversion + caching
│   │   └── store.py           # Qdrant vector store operations
│   │
│   └── routers/               # FastAPI route handlers (endpoints)
│       ├── ask.py             # POST /ask, /ask/grounded
│       ├── search.py          # GET /search (retrieval debugging)
│       ├── ingest.py          # POST /ingest (load & embed documents)
│       ├── inspect.py         # GET /store/inspect (inspect vector store)
│       └── embed.py           # POST /embed (embedding explorer)
│
├── data/                      # Data pipeline stages
│   ├── raw/                   # Original unprocessed documents
│   ├── processed/             # Cleaned & transformed documents
│   └── knowledge/             # Source documents ready for ingestion
│       ├── *.md, *.txt        # Markdown & text files
│       ├── *.csv              # CSV → "Column: Value" format
│       ├── *.pdf              # PDF text extraction
│       └── *.json             # Flattened JSON key-value pairs
│
├── frontend/                  # React + Vite SPA
│   ├── src/
│   │   ├── App.jsx            # Main UI layout
│   │   ├── api.js             # Axios client for backend
│   │   ├── tabs/              # Tab panels for each endpoint
│   │   └── components/        # Reusable UI components
│   └── nginx.conf             # Production proxy config
│
├── pyproject.toml             # Python dependencies (FastAPI, Qdrant, etc.)
├── Dockerfile                 # Backend containerization
├── docker-compose.yml         # Full stack orchestration
├── backend/Dockerfile         # Backend image (FastAPI + Python)
├── frontend/Dockerfile        # Frontend image (React + Nginx)
└── README.md                  # Project documentation

```

**Key Directory Rules:**
- **`backend/`**: All Python business logic. Never mix frontend concerns.
- **`backend/rag/`**: Pure RAG pipeline logic. Should be reusable in non-web contexts.
- **`backend/routers/`**: HTTP endpoints only. Thin layer orchestrating RAG modules.
- **`data/raw/`**: Original source documents (immutable).
- **`data/processed/`**: Cleaned & transformed documents (intermediate).
- **`data/knowledge/`**: Production-ready document files for ingestion. Can be edited/added without code changes.

---

## Architectural Overview

### High-Level Flow

```
User Request
    ↓
FastAPI Router (HTTP → Python)
    ↓
RAG Module (specific operation)
    ├─ Loader:   Files → Plain Text
    ├─ Chunker:  Text → Overlapping Chunks
    ├─ Embedder: Chunks → Vectors
    ├─ Store:    Vectors ⇄ Qdrant
    └─ LLM:      Prompt → Response
    ↓
Pydantic Model (Python → JSON)
    ↓
HTTP Response (JSON)
```

### Core Concepts

**1. Vector Embeddings**
- Convert text into vectors (lists of floats) that capture semantic meaning
- Similar meanings = similar vectors (measured by distance/similarity)
- Critical for semantic search without keywords

**2. Chunking**
- Documents are too large to embed and search reliably as wholes
- Split depending on use case
- Sentence-aware boundaries prevent mid-sentence cuts

**3. Vector Store (Qdrant)**
- Stores chunks + their embeddings + metadata
- Cosine distance metric for text (standard in NLP)
- Upsert pattern: re-ingesting updates existing chunks (no duplicates)
- Persistent database with JSON config for flexible schema management

**4. Retrieval + Generation (RAG)**
- Query → Embed → Search store → Get top-k chunks → Inject into LLM prompt → Generate
- Grounds LLM responses in your documents

---

## RAG Pipeline Best Practices

### 1. **Loader Module** (`backend/rag/loader.py`)

**Design Philosophy:**
- Convert ALL file formats to plain text
- Keep the chunker simple (text-only input)
- Format-specific logic isolated in loader

**Best Practices:**

```python
# ✅ GOOD: Dispatch on extension, handle each format
def load_file(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return _load_pdf(path)
    elif ext == ".csv":
        return _load_csv(path)
    # etc.

# ❌ BAD: Try to handle all formats in one function
def load_file(path: str) -> Any:
    data = magic_loader(path)  # what does this return?
    return data  # Could be PDF bytes, dict, list...
```

**Common Patterns:**
- **CSV:** Convert to "Column: Value" blocks (human-readable)
- **PDF:** Extract text per page, join with `\n\n`
- **JSON:** Flatten nested dicts to "key: value" lines
- **Markdown/Text:** Read as-is

**Failure Handling:**
```python
try:
    from pypdf import PdfReader
except ImportError:
    return f"[PDF file: {filepath.name} — install pypdf to extract text]"
```
Graceful degradation: inform users which packages are missing.

---

### 2. **Chunker Module** (`backend/rag/chunker.py`)

**Design Philosophy:**
- Independent of file type (works on plain text)
- Sentence-aware boundaries (better embeddings)
- Meaningful overlaps (preserve context at boundaries)

**Best Practices:**

```python
# ✅ GOOD: Sentence-aware boundary detection
end = text.rfind(". ", start, end)  # Find last sentence boundary
if last_break > start:
    end = last_break + 2  # Include ". "

# ❌ BAD: Naive fixed-size windows
end = min(start + chunk_size, len(text))
# Risk: cuts mid-sentence, poor embeddings
```

**Configuration Tradeoffs:**

| Config | Pros | Cons |
|--------|------|------|
| **Small (200 chars)** | Precise retrieval | Less context, fragmented |
| **Medium (500 chars)** | ✅ Sweet spot | Balanced |
| **Large (1000+ chars)** | Rich context | Noisy retrieval, slow |

**Always tune based on domain:**
- **Legal docs:** Larger (need full clauses)
- **FAQs:** Smaller (Q&A pairs)

---

### 3. **Embedder Module** (`backend/rag/embedder.py`)

**Design Philosophy:**
- Cached client factories (reuse HTTP connections)
- Provider-agnostic (Gemini / OpenAI / Azure)
- Retry logic for transient failures
- Batch operations for efficiency

**Best Practices:**

```python
# ✅ GOOD: Cached, reusable client
@lru_cache(maxsize=1)
def _get_openai_client():
    return OpenAI(api_key=OPENAI_API_KEY)

# ❌ BAD: New client per call
def embed_text(text):
    client = OpenAI(api_key=OPENAI_API_KEY)  # ← expensive!
    return client.embeddings.create(...)

# ✅ GOOD: Batch embeddings to reduce API calls
embeddings = embed_texts(chunk_texts)  # one API call

# ❌ BAD: Embed one at a time
embeddings = [embed_text(chunk) for chunk in chunks]  # N API calls
```

**Retry Strategy:**
```python
for attempt in range(LLM_MAX_RETRIES):
    try:
        return _do_embedding(...)
    except Exception as e:
        if attempt == LLM_MAX_RETRIES - 1:
            raise
        time.sleep(LLM_RETRY_DELAY * (2 ** attempt))  # Exponential backoff
```

**Provider Selection:**
- **Gemini:** Free tier generous, embedding model included
- **OpenAI:** More stable, better embeddings, costs more
- **Azure:** Enterprise support, need Azure setup

---

### 4. **Store Module** (`backend/rag/store.py`)

**Design Philosophy:**
- Thin wrapper around Qdrant vector database
- Cosine metric for text (not L2/Euclidean)
- Metadata preservation (source, chunk_index)
- Upsert for idempotent ingestion
- RESTful API for flexibility

**Best Practices:**

```python
# ✅ GOOD: Cosine distance for embeddings (Qdrant default)
vector_config = VectorParams(
    size=embedding_size,
    distance=Distance.COSINE  # ← Standard for text embeddings
)

# ❌ BAD: Using Euclidean distance for embeddings
# Variant to magnitude; semantically incorrect for text

# ✅ GOOD: Meaningful IDs for deduplication
point_ids = [f"{source}_{chunk_index}" for chunk in chunks]
qdrant_client.upsert(
    collection_name="knowledge",
    points=points
)  # Re-ingest safely

# ❌ BAD: Random/counting IDs
point_ids = [str(i) for i in range(len(chunks))]  # Lost source info!
```

**Search Behavior:**
```python
distance < 0.4  → Very relevant (similar meaning)
0.4 < distance < 0.7  → Similar
distance > 1.0  → Likely irrelevant

# Always check: min(actual_k, n_stored) to avoid crashes
```

---

### 5. **Embedder + Store Integration**

**Complete RAG Ingestion Flow:**

```python
# backend/routers/ingest.py

1. Load files
   ├─ Read file (format-specific)
   └─ Output: plain text

2. Chunk
   ├─ Split into overlapping chunks
   └─ Output: [{"text": ..., "source": ..., "chunk_index": ...}]

3. Embed
   ├─ Get vectors for all chunks (batched)
   └─ Output: [[float, float, ...], ...]  ← One per chunk

4. Store
   ├─ Upsert chunks + embeddings into Qdrant
   └─ Side effect: persistent qdrant_data/ directory
```

**Error Handling Pattern:**
```python
if not knowledge_path.exists():
    return IngestResponse(files_processed=0, ...)  # Graceful empty

try:
    text = load_file(str(filepath))
except Exception as e:
    logger.warning(f"Failed to load {filepath}: {e}")
    continue  # Skip, move to next file
```

---

## FastAPI Best Practices

### 1. **Route Organization** (`backend/routers/`)

**Design Philosophy:**
- One router per logical endpoint group
- Handlers are thin (delegate to RAG modules)
- Type hints & Pydantic models for validation

**File Structure:**
```python
# backend/routers/ask.py

from fastapi import APIRouter
from backend.models import Question, Answer
from backend.llm import call_llm

router = APIRouter(prefix="/ask", tags=["Q&A"])

@router.post("", response_model=Answer)
def ask_plain(request: Question):
    """Ask a question — answered by LLM only."""
    response_text = call_llm(request.question)
    return Answer(answer=response_text, ...)
```

**Best Practices:**

```python
# ✅ GOOD: Response model declares contract
@router.get("/search", response_model=SearchResponse)
def search(q: str): ...

# ❌ BAD: Untyped response
@router.get("/search")
def search(q: str) -> dict: ...  # What keys in dict?

# ✅ GOOD: Query parameters with descriptions
@router.get("", response_model=SearchResponse)
def search(
    q: str = Query(description="The search query text."),
    top_k: int = Query(default=3, description="Number of results."),
): ...

# ❌ BAD: Opaque parameters
def search(q, top_k=3): ...
```

### 2. **Models** (`backend/models.py`)

**Design Philosophy:**
- One Pydantic model per request/response
- Document with docstrings
- Use simple types (str, int, float, list, dict)

**Structure:**

```python
class Question(BaseModel):
    """A user question sent to the assistant."""
    question: str

class Answer(BaseModel):
    """LLM response — may or may not be grounded."""
    answer: str
    model: str
    grounded: bool = False  # Default value

class SearchResult(BaseModel):
    """Single search result from vector store."""
    text: str
    source: str
    chunk_index: int
    distance: float  # Cosine distance [0, 2]
```

**Best Practices:**

```python
# ✅ GOOD: Descriptive, reusable models
class ChunkInfo(BaseModel):
    text: str
    source: str
    chunk_index: int

# ✅ GOOD: Models composed from simpler models
class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total_results: int

# ❌ BAD: Deeply nested inline models
@router.get("/search")
def search() -> dict:
    return {
        "query": q,
        "results": [{"text": t, "source": s, ...} for ...],
    }
```

### 3. **Main App** (`backend/main.py`)

**Design Philosophy:**
- Minimal business logic (just setup)
- CORS configured for dev + production
- Logging setup at module level
- Routes registered clearly

**Structure:**

```python
# backend/main.py

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Logging setup (before imports to catch all modules)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-18s | %(levelname)-5s | %(message)s",
)

# Suppress unneeded telemetry logging
logging.getLogger("qdrant_client").setLevel(logging.WARNING)

# Import routers
from backend.routers.ask import router as ask_router
from backend.routers.search import router as search_router

# Create app
app = FastAPI(title="...", description="...", version="1.0.0")

# CORS middleware
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(ask_router)
app.include_router(search_router)

# Health check
@app.get("/health")
def health():
    return {"status": "ok"}
```

**Best Practices:**

```python
# ✅ GOOD: Suppress unneeded telemetry logging
logging.getLogger("qdrant_client").setLevel(logging.WARNING)

# ✅ GOOD: CORS origins from environment
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "default").split(",")

# ❌ BAD: Hardcoded CORS (breaks production)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"])
```

### 4. **Config** (`backend/config.py`)

**Design Philosophy:**
- Load all config from environment variables
- Provide sensible defaults
- Single source of truth

**Pattern:**

```python
from dotenv import load_dotenv
import os

load_dotenv()  # Load .env file

# LLM provider selection
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")

# Provider-specific keys
if LLM_PROVIDER == "openai":
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# Data paths
KNOWLEDGE_DIR = os.getenv("KNOWLEDGE_DIR", "data/knowledge")

# Vector store settings
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "knowledge")

# Constants for chunking
DEFAULT_CHUNK_SIZE = int(os.getenv("DEFAULT_CHUNK_SIZE", "500"))
DEFAULT_CHUNK_OVERLAP = int(os.getenv("DEFAULT_CHUNK_OVERLAP", "50"))
```

**Best Practices:**

```python
# ✅ GOOD: Load once, reuse everywhere
from backend.config import GEMINI_API_KEY
# (not os.getenv("GEMINI_API_KEY") everywhere)

# ✅ GOOD: Sensible defaults (guards against missing .env)
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))

# ❌ BAD: No default (crashes if env var missing)
CRITICAL_VALUE = int(os.getenv("CRITICAL_VALUE"))  # Oops!
```

---

## RAG-FastAPI Communication Patterns

### 1. **Request Flow: Frontend → FastAPI → RAG**

```
POST /search?q=vacation%20policy
    ↓
[backend/routers/search.py]
    search_chunks(q: str) function
    ↓
[backend/rag/embedder.py]
    embed_text(q) → Vector[float]
    ↓
[backend/rag/store.py]
    search(query_embedding, top_k=3) → List[Dict]
    ↓
[backend/routers/search.py]
    Convert Dicts → SearchResult objects
    ↓
HTTP 200 + SearchResponse JSON
    {
        "query": "vacation policy",
        "results": [...],
        "total_results": 3
    }
```

### 2. **Data Transformation Pipeline**

**Frontend (JSON) → FastAPI (Python) → Backend (Objects) → HTTP (JSON)**

```python
# User sends: {"question": "What's the leave policy?"}

# 1. FastAPI deserializes (Pydantic)
class Question(BaseModel):
    question: str
request: Question  # ← Validated, typed

# 2. Pass to RAG
response_text = call_llm(request.question)

# 3. Create response model
return Answer(answer=response_text, model="gemini-2.5-flash", grounded=True)

# 4. FastAPI serializes to JSON
# Auto → {"answer": "...", "model": "...", "grounded": true}
```

### 3. **RAG Module Encapsulation**

**Rule: RAG modules are HTTP-agnostic**

```python
# ✅ GOOD: embedder.py doesn't know about HTTP
def embed_text(text: str) -> list[float]:
    """Pure function: text → vector."""
    # No requests, no FastAPI, no JSON
    return [0.1, 0.2, 0.3, ...]

# ✅ GOOD: Router encapsulates HTTP ceremony
@router.get("")
def search(q: str):
    embedding = embed_text(q)  # Call RAG
    results = store.search(embedding)  # Call RAG
    return SearchResponse(...)  # Wrap for HTTP

# ❌ BAD: RAG module requires HTTP
def embed_text(request: Request) -> Response:
    # Tight coupling to HTTP layer
```

**Benefit:** RAG can be used in CLI, scripts, batch jobs, etc.

### 4. **Error Handling: RAG Errors → HTTP Status**

```python
# backend/routers/ingest.py

@router.post("/ingest", response_model=IngestResponse)
def ingest():
    try:
        # RAG pipeline
        documents = load_all_files()
        chunks = chunk_all(documents)
        embeddings = embed_all(chunks)
        store.add_chunks(chunks, embeddings)
    except FileNotFoundError:
        # Return graceful response (HTTP 200 with empty data)
        return IngestResponse(files_processed=0, chunks_stored=0, ...)
    except ValueError as e:
        # Client error: invalid input
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Server error: unexpected failure
        raise HTTPException(status_code=500, detail="Ingestion failed")
```

**Status Code Guidelines:**
- **200:** Success (or success with no data)
- **400:** Client error (bad request, invalid file type)
- **500:** Server error (API key missing, ingestion crashed)

### 5. **Stateless Design Pattern**

**Rule: Each request is independent**

```python
# ✅ GOOD: Stateless
@router.get("/search")
def search(q: str):
    # No global state modified
    # No session storage
    # HTTP clients can retry safely
    return search_store(q)

# ❌ BAD: Stateful (breaks scaling)
SEARCH_CACHE = {}

@router.get("/search")
def search(q: str):
    if q not in SEARCH_CACHE:
        SEARCH_CACHE[q] = search_store(q)
    return SEARCH_CACHE[q]
    # ← Doesn't work across multiple processes/containers!
```

---

## Coding Methodology

### 1. **Module Responsibilities**

| Module | Input | Output | Side Effects |
|--------|-------|--------|--------------|
| **loader** | File path | Plain text | I/O |
| **chunker** | Text + params | List[Chunk] | None |
| **embedder** | Text list | Vector list | API calls |
| **store** | Chunks + vectors | Count | Qdrant writes |
| **router** | HTTP request | HTTP response | Logging |
| **llm** | Prompt | Text | API calls |

### 2. **Function Design Principles**

**SRP (Single Responsibility):**
```python
# ✅ GOOD: One function, one job
def embed_text(text: str) -> list[float]:
    """Convert text to embedding vector."""

def add_chunks(chunks: list[dict], embeddings: list[list[float]]) -> int:
    """Store chunks in vector store. Return count."""

# ❌ BAD: Multiple jobs
def ingest(file_path, model="gemini"):
    text = load_file(file_path)
    chunks = chunk(text)
    embeddings = embed_chunk(chunks)
    store(embeddings)
    display(len(chunks))  # I/O mixed with logic!
```

**Pure Functions (preferred):**
```python
# ✅ GOOD: Pure (no side effects)
def chunk_document(text: str, chunk_size: int) -> list[dict]:
    """Split text. Input determines output fully."""
    return [{"text": t, ...} for t in chunks]

# ⚠️ MIXED: API call (acceptable, documented)
def call_llm(prompt: str) -> str:
    """Send prompt to LLM. Side effect: external API call."""
    response = client.chat.completions.create(...)
    return response.content

# ❌ BAD: Hidden side effects
def chunk_document(text):
    chunks = split(text)
    save_to_db(chunks)  # ← Unexpected!
    return chunks
```

### 3. **Error Handling Strategy**

**Hierarchy:**
1. **Prevent:** Validate inputs (Pydantic)
2. **Handle:** Use try/except for expected failures
3. **Log:** Always log failures with context
4. **Fail safely:** Return empty data, not exception

```python
# backend/routers/ingest.py

@router.post("/ingest")
def ingest(chunk_size: int = 500):
    # 1. Prevent: Pydantic validates chunk_size type
    if chunk_size < 100:
        raise ValueError("chunk_size must be >= 100")
    
    # 2. Handle expected failures
    knowledge_path = Path(KNOWLEDGE_DIR)
    if not knowledge_path.exists():
        logger.warning(f"Knowledge dir missing: {knowledge_path}")
        return IngestResponse(files_processed=0, ...)
    
    # 3. Log & fail safely
    for file in knowledge_path.iterdir():
        try:
            text = load_file(str(file))
        except Exception as e:
            logger.warning(f"Failed to load {file}: {e}")
            continue  # Skip, move to next
    
    return IngestResponse(...)
```

### 4. **Logging Best Practices**

**Setup Once:**
```python
# backend/main.py

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-18s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)

# Suppress noisy libraries
logging.getLogger("qdrant_client").setLevel(logging.WARNING)
```

**Use Module Loggers:**
```python
# backend/routers/ingest.py

logger = logging.getLogger("rag.ingest")

logger.info("Ingest started | files=%d chunks=%d", len(files), len(chunks))
logger.warning("File not found: %s", filepath)
logger.error("Embedding failed", exc_info=True)
```

**Log Lifecycle Events:**
```python
logger.info("Ingest started | strategy=%s chunk_size=%d", strategy, chunk_size)
logger.info("Chunking complete | %d files -> %d chunks", files, chunks)
logger.info("Embedding complete | %d vectors", len(embeddings))
logger.info("Storage complete | %d chunks stored", stored)
```

---

## Common Patterns & Anti-Patterns

### Pattern 1: RAG Query (Search → Retrieve → Inject)

**✅ GOOD:**
```python
@router.post("/ask/grounded")
def ask_grounded(request: Question):
    # 1. Embed query
    query_embedding = embed_text(request.question)
    
    # 2. Retrieve chunks
    relevant_chunks = search(query_embedding, top_k=3)
    
    # 3. Inject into prompt
    context = "\n\n".join([c["text"] for c in relevant_chunks])
    system_prompt = f"Use this context:\n{context}"
    
    # 4. Call LLM
    response = call_llm(
        user_prompt=request.question,
        system_prompt=system_prompt,
    )
    
    return Answer(answer=response, grounded=True)
```

### Pattern 2: Batch Processing

**✅ GOOD:**
```python
# backend/rag/embedder.py

def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed multiple texts in one API call."""
    client = _get_openai_client()
    response = client.embeddings.create(
        input=texts,
        model=OPENAI_EMBEDDING_MODEL,
    )
    return [item.embedding for item in response.data]
```

**❌ BAD:**
```python
def embed_texts(texts):
    return [embed_text(text) for text in texts]  # N API calls!
```

### Pattern 3: Metadata Preservation

**✅ GOOD:**
```python
# backend/rag/store.py

ids = [f"{c['source']}_{c['chunk_index']}" for c in chunks]
metadatas = [{"source": c["source"], "chunk_index": c["chunk_index"]} for c in chunks]

collection.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
```

**Traceability:** Know exactly which document each result came from.

### Pattern 4: Configuration Injection

**✅ GOOD:**
```python
# backend/routers/ingest.py

@router.post("/ingest")
def ingest_documents(
    chunk_size: int = Query(default=DEFAULT_CHUNK_SIZE),
    overlap: int = Query(default=DEFAULT_CHUNK_OVERLAP),
):
    # Use provided params, or defaults
    chunks = chunk_document(text, chunk_size=chunk_size, overlap=overlap)
```

**❌ BAD:**
```python
def ingest_documents():
    from backend.config import DEFAULT_CHUNK_SIZE
    chunks = chunk_document(text, chunk_size=DEFAULT_CHUNK_SIZE)
    # ← No way for user to override!
```

### Anti-Pattern 1: Mixing Concerns

**❌ BAD:**
```python
def ingest_and_respond(filepath):
    # This function does too much:
    text = load_file(filepath)  # I/O
    chunks = chunk(text)  # Compute
    embeddings = embed(chunks)  # API
    store.add(chunks, embeddings)  # DB
    
    # Then returns a web response ← HTTP!
    return {"status": "ok", "chunks": len(chunks)}
```

**✅ GOOD:**
```python
# Separate concerns:

# 1. RAG logic (testable, reusable)
def ingest_and_store(filepath):
    text = load_file(filepath)
    chunks = chunk(text)
    embeddings = embed(chunks)
    return store.add(chunks, embeddings)

# 2. HTTP handler (orchestrates RAG)
@router.post("/ingest")
def ingest_documents(filepath):
    count = ingest_and_store(filepath)
    return IngestResponse(chunks_stored=count, ...)
```

### Anti-Pattern 2: Global State

**❌ BAD:**
```python
# backend/rag/store.py

COLLECTION = None  # ← Shared state!

def get_collection():
    global COLLECTION
    if COLLECTION is None:
        COLLECTION = get_or_create(...)
    return COLLECTION
```

**Why bad:** Doesn't work with async, multiprocessing, or testing.

**✅ GOOD:**
```python
def get_collection():
    """Fetch fresh each time (Qdrant handles internal caching)."""  
    client = get_client()
    return client.get_or_create_collection(...)
```

### Anti-Pattern 3: Silent Failures

**❌ BAD:**
```python
def load_all_files():
    files = []
    for path in knowledge_dir.iterdir():
        try:
            text = load_file(path)
            files.append(text)
        except:
            pass  # ← Silent! User has no idea what failed.
    return files
```

**✅ GOOD:**
```python
def load_all_files():
    files = []
    for path in knowledge_dir.iterdir():
        try:
            text = load_file(path)
            files.append(text)
        except Exception as e:
            logger.warning(f"Failed to load {path}: {e}")
            # Continue processing others
    
    if not files:
        logger.error("No files loaded from %s", knowledge_dir)
    
    return files
```

---

## Testing Mindset

Document how modules should be tested:

```python
# ✅ GOOD: Pure functions are easy to test
def test_chunk_document():
    text = "Hello. World. Test."
    chunks = chunk_document(text, chunk_size=10)
    assert len(chunks) == 2
    assert chunks[0]["text"] in text  # Content preserved

# ⚠️ ACCEPTABLE: Mock external APIs
def test_embed_text(mock_openai):
    mock_openai.embeddings.create.return_value = Mock(data=[Mock(embedding=[...])])
    result = embed_text("hello")
    assert len(result) == 3  # Our embedding is 3-dimensional
    mock_openai.embeddings.create.assert_called_once()

# ✅ GOOD: Integration tests for full flows
def test_ingest_and_search(tmp_path):
    # Set up: Create a test document
    test_file = tmp_path / "test.md"
    test_file.write_text("Vacation day info...")
    
    # Execute: Ingest
    count = ingest_and_store(str(test_file))
    
    # Verify: Search finds it
    results = search(embed_text("vacation"))
    assert len(results) > 0
    assert "vacation" in results[0]["text"].lower()
```

---

## Summary: The RAG-FastAPI Design

| Layer | Responsibility | Example |
|-------|-----------------|---------|
| **HTTP** | Validate input, serialize output | Pydantic models, FastAPI routers |
| **FastAPI Router** | Orchestrate RAG calls, error handling | `backend/routers/*.py` |
| **RAG Modules** | Pure logic, composable, testable | `backend/rag/*.py` |
| **External APIs** | Vendor clients, cached & retried | Gemini, OpenAI, Qdrant |

**Key Principles:**
1. Separate concerns (HTTP ≠ RAG logic)
2. RAG modules are reusable (could be CLI, API, batch)
3. Type everything (Pydantic, type hints)
4. Log lifecycle events
5. Fail safely (graceful empty responses)
6. Test pure functions thoroughly
7. Document tradeoffs (chunking params, model selection)

---

## Quick Reference Commands

```bash
# Activate venv
source .venv/bin/activate

# Run locally
uv run uvicorn backend.main:app --reload

# Ingest documents
curl -X POST http://localhost:8000/ingest

# Search vector store
curl http://localhost:8000/search?q=vacation%20policy

# Build & run full stack
docker compose up --build
```

---

**Version:** 1.0.0  
**Last Updated:** April 2026  
**Author:** AI SEF Bootcamp Mentors
