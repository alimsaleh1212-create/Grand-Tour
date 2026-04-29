"""Vector store dependency.

Implemented in Stage 4.

Public surface (planned):
    async def get_vector_store(request: Request) -> VectorStore:
        return request.app.state.vector_store

The vector store wraps the pgvector-backed Embedding table and exposes
`async upsert(...)` and `async search(query_vector, top_k)` methods. It
is constructed once in lifespan startup (after the engine is up) and
parked on `app.state.vector_store`.
"""
