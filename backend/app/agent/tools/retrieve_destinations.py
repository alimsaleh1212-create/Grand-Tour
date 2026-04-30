"""Tool 1 — retrieve_destinations: embed query → pgvector cosine search.

The embedder and store are injected at construction time.  This tool never
builds its own clients — lifecycle is owned by the FastAPI lifespan handler.

PUBLIC SURFACE
--------------
    class RetrieveQuery(BaseModel)
    class RetrievedChunk(BaseModel)
    class RetrieveResult(BaseModel)
    class RetrieveDestinationsTool(BaseTool[RetrieveQuery, RetrieveResult])
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from app.agent.tools.base import BaseTool
from app.rag.embedder import GeminiEmbedder
from app.rag.store import VectorStore

log = logging.getLogger(__name__)


# ── Pydantic schemas ───────────────────────────────────────────────────────────


class RetrieveQuery(BaseModel):
    """Input schema for the retrieve_destinations tool.

    Attributes:
        query_text: The natural-language query to embed and search.
        top_k: Maximum number of chunks to return.
    """

    query_text: str = Field(..., min_length=3, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)


class RetrievedChunk(BaseModel):
    """One result from the vector similarity search.

    Fields match SearchHit so the LLM receives fully structured citations
    without any prose-parsing.
    """

    source: str
    chunk_index: int
    text: str
    distance: float
    section: str
    destination: str
    source_url: str


class RetrieveResult(BaseModel):
    """Output schema for the retrieve_destinations tool."""

    query: str
    chunks: list[RetrievedChunk]


# ── Tool implementation ────────────────────────────────────────────────────────


class RetrieveDestinationsTool(BaseTool[RetrieveQuery, RetrieveResult]):
    """Embed a query with Gemini and retrieve similar chunks from pgvector.

    Args:
        embedder: GeminiEmbedder singleton (injected from lifespan).
        store: VectorStore singleton (injected from lifespan).
    """

    name = "retrieve_destinations"
    input_schema = RetrieveQuery
    output_schema = RetrieveResult

    def __init__(self, embedder: GeminiEmbedder, store: VectorStore) -> None:
        self._embedder = embedder
        self._store = store

    async def run(self, args: RetrieveQuery) -> RetrieveResult:
        """Embed the query and search pgvector.

        Args:
            args: Validated query + top_k.

        Returns:
            RetrieveResult with ranked chunks carrying destination metadata.
        """
        vector = await self._embedder.embed_text(
            args.query_text, task_type="RETRIEVAL_QUERY"
        )
        hits = await self._store.search(vector, top_k=args.top_k)

        log.info(
            "tool.retrieve_destinations.success",
            extra={"query": args.query_text[:80], "hits": len(hits)},
        )

        return RetrieveResult(
            query=args.query_text,
            chunks=[
                RetrievedChunk(
                    source=h.source,
                    chunk_index=h.chunk_index,
                    text=h.text,
                    distance=h.distance,
                    section=h.section,
                    destination=h.destination,
                    source_url=h.source_url,
                )
                for h in hits
            ],
        )
