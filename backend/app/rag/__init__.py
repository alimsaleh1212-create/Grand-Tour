"""Runtime RAG pipeline modules.

Per the mentor guidelines: each module is HTTP-agnostic so it could be
reused from a CLI or a script. Modules:

    loader.py    plain-text loaders for .md/.txt/.pdf/.csv/.json source
                 documents. Dispatches on file extension.
    chunker.py   sentence-aware splitter producing overlapping windows.
                 Pure function: text -> list[ChunkRecord].
    embedder.py  async HTTP client to the local Ollama server. Batched.
                 Returns list[list[float]] aligned with the input texts.
    store.py     pgvector ops via async SQLAlchemy: upsert(chunks,
                 vectors), search(query_vector, top_k).

The CLI `rag/scripts/ingest.py` glues them together for the one-shot
ingestion job. The agent's `retrieve_destinations` tool consumes the same
embedder + store at request time.
"""
