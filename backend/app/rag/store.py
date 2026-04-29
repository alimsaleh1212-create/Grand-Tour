"""Vector store — pgvector cosine similarity via async SQLAlchemy.

Design decisions:
    Cosine distance (<=> operator) is standard for text embeddings because
    it measures angular similarity independent of vector magnitude.

    Deterministic IDs on (source, chunk_index) make re-ingestion idempotent:
    re-running the ingest script on an unchanged document replaces the
    existing embedding instead of creating a duplicate row.

    top_k results are clamped to the actual row count to avoid crash when
    the store is smaller than the requested k.

    destination and source_url are stored as top-level columns (not buried
    in the text payload) so the retrieve tool can return them as structured
    citation fields.  The destination field is passed directly to the
    classify_style tool — no prose parsing required.

PUBLIC SURFACE
--------------
    @dataclass
    class SearchHit:
        source, chunk_index, text, distance,
        section, destination, source_url

    class VectorStore:
        async def upsert(chunks, vectors) -> int
        async def search(query_vector, top_k, similarity_threshold) -> list[SearchHit]
        async def count() -> int
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.embedding import Embedding
from app.rag.chunker import ChunkRecord


@dataclass
class SearchHit:
    """One result from a vector similarity search.

    Fields are structured so the retrieve tool can return them directly as
    citation metadata without any post-processing or prose parsing.
    """

    source: str
    chunk_index: int
    text: str
    distance: float
    section: str
    destination: str
    source_url: str


class VectorStore:
    """pgvector-backed store for knowledge chunk embeddings."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def upsert(
        self,
        chunks: Sequence[ChunkRecord],
        vectors: Sequence[Sequence[float]],
    ) -> int:
        """Insert or update (source, chunk_index) rows.

        Args:
            chunks: ChunkRecord list from the chunker.
            vectors: Embedding vectors — parallel to chunks (same length).

        Returns:
            Number of rows inserted or updated.

        Raises:
            ValueError: If len(chunks) != len(vectors).
        """
        if len(chunks) != len(vectors):
            raise ValueError(
                f"chunks ({len(chunks)}) and vectors ({len(vectors)}) must be same length"
            )
        if not chunks:
            return 0

        rows = [
            {
                "source": c.source,
                "chunk_index": c.chunk_index,
                "text": c.text,
                "section": c.section,
                "destination": c.destination,
                "source_url": c.source_url,
                "vector": list(v),
            }
            for c, v in zip(chunks, vectors)
        ]

        stmt = pg_insert(Embedding).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_embeddings_source_chunk",
            set_={
                "text": stmt.excluded.text,
                "section": stmt.excluded.section,
                "destination": stmt.excluded.destination,
                "source_url": stmt.excluded.source_url,
                "vector": stmt.excluded.vector,
            },
        )

        async with self._sessionmaker() as session:
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount

    async def search(
        self,
        query_vector: Sequence[float],
        top_k: int = 5,
        similarity_threshold: float = 1.5,
    ) -> list[SearchHit]:
        """Return the top_k most similar chunks by cosine distance.

        Args:
            query_vector: Embedding of the search query (task_type=RETRIEVAL_QUERY).
            top_k: Number of results to return.
            similarity_threshold: Maximum cosine distance to include (0=identical,
                2=opposite). Default 1.5 is permissive; tighten to 0.7 for
                high-precision retrieval.

        Returns:
            List of SearchHit ordered by ascending distance (most similar first).
            Each hit carries destination and source_url as structured citation
            fields — the caller does not need to parse the text to cite the source.
        """
        async with self._sessionmaker() as session:
            total = await session.scalar(select(func.count()).select_from(Embedding))
            if not total:
                return []
            k = min(top_k, total)

            distance_col = Embedding.vector.cosine_distance(list(query_vector))
            stmt = (
                select(
                    Embedding.source,
                    Embedding.chunk_index,
                    Embedding.text,
                    Embedding.section,
                    Embedding.destination,
                    Embedding.source_url,
                    distance_col.label("distance"),
                )
                .where(distance_col <= similarity_threshold)
                .order_by(distance_col)
                .limit(k)
            )
            rows = (await session.execute(stmt)).all()

        return [
            SearchHit(
                source=r.source,
                chunk_index=r.chunk_index,
                text=r.text,
                distance=float(r.distance),
                section=r.section,
                destination=r.destination,
                source_url=r.source_url,
            )
            for r in rows
        ]

    async def count(self) -> int:
        """Return total number of stored embedding rows."""
        async with self._sessionmaker() as session:
            return (
                await session.scalar(select(func.count()).select_from(Embedding))
            ) or 0
