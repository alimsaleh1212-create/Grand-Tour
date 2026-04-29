"""One-shot ingestion CLI: knowledge files → pgvector store.

Implemented in Stage 4.

Usage (planned):
    uv run python -m rag.scripts.ingest                       # all files
    uv run python -m rag.scripts.ingest --paths tokyo.md ...  # selected

Pipeline:
    1. Iterate `rag/data/knowledge/*.{md,txt,pdf,csv,json}`.
    2. For each file: `loader.load_file()` → plain text.
    3. `chunker.chunk_document()` with chunk_size / overlap from Settings.
    4. `embedder.embed_texts()` — async, batched against local Ollama.
    5. `store.upsert(chunks, vectors)` — idempotent on (source,
       chunk_index).
    6. Print summary: files processed, chunks added, chunks updated,
       elapsed seconds.

This script is what we'll run before opening the demo to populate the
pgvector store. Re-running it after editing a source file updates only
the affected rows.

Why it lives outside `backend/`: the brief asks for a real engineering
layout — ingestion is an offline batch job, not a request handler, so
it gets its own entry point.
"""
