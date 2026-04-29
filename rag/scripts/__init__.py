"""Stand-alone RAG scripts.

These run outside the FastAPI process (as one-shot CLI jobs) but reuse
the same `backend.app.rag` modules to keep loader/chunker/embedder/store
behaviour identical between ingestion and request-time retrieval.
"""
