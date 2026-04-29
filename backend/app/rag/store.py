"""Vector store — pgvector ops via async SQLAlchemy.

Implemented in Stage 4.

Design:
    * Cosine distance (`<=>` operator under pgvector) is the standard for
      text embeddings.
    * Deterministic IDs use composite (source, chunk_index) so re-ingestion
      is idempotent — `INSERT ... ON CONFLICT (source, chunk_index) DO
      UPDATE` re-uses the existing row instead of creating duplicates.
    * Top-k searches clamp to `min(top_k, count(*))` to avoid edge-case
      crashes when the store is small.

Public surface (planned):
    @dataclass
    class SearchHit:
        source: str
        chunk_index: int
        text: str
        distance: float

    class VectorStore:
        def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]): ...

        async def upsert(
            self,
            chunks: Sequence[ChunkRecord],
            vectors: Sequence[Sequence[float]],
        ) -> int: ...

        async def search(
            self,
            query_vector: Sequence[float],
            top_k: int = 5,
        ) -> list[SearchHit]: ...

        async def count(self) -> int: ...
"""
