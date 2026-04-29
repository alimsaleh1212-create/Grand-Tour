"""Async embedding client — Google Gemini text-embedding-004 (768-dim).

WHY GEMINI EMBEDDINGS INSTEAD OF LOCAL OLLAMA
----------------------------------------------
Render deployments have no GPU and no persistent sidecar process for Ollama.
The Gemini Embedding API (`text-embedding-004`) requires no infrastructure
beyond a GOOGLE_API_KEY, produces 768-dimensional vectors (matching the
pgvector column already created in migration), and is available on Render's
free tier within the Google AI Studio quota.

TASK TYPES
----------
The Gemini embedding API supports task_type hints that produce better vectors:
    RETRIEVAL_DOCUMENT  — used at ingest time (knowledge chunks)
    RETRIEVAL_QUERY     — used at query time (user question)
The embedder accepts task_type as an argument; callers must pass the right one.

PUBLIC SURFACE
--------------
    class GeminiEmbedder:
        async def embed_text(text, task_type) -> list[float]
        async def embed_texts(texts, task_type) -> list[list[float]]

    def get_embedder(api_key, model, embed_dim) -> GeminiEmbedder
        # Cached singleton — call once; reuse everywhere.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Literal

import google.generativeai as genai

TaskType = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY", "SEMANTIC_SIMILARITY"]

_BATCH_SIZE = 100  # Gemini embedding API limit per request


class GeminiEmbedder:
    """Thin async wrapper around the Gemini embedding API.

    The underlying SDK call is synchronous, so embed_texts runs it in a
    thread pool to avoid blocking the event loop.
    """

    def __init__(self, *, api_key: str, model: str, embed_dim: int) -> None:
        genai.configure(api_key=api_key)
        self._model = model
        self._embed_dim = embed_dim

    async def embed_text(
        self, text: str, task_type: TaskType = "RETRIEVAL_DOCUMENT"
    ) -> list[float]:
        """Embed a single string."""
        results = await self.embed_texts([text], task_type=task_type)
        return results[0]

    async def embed_texts(
        self,
        texts: list[str],
        task_type: TaskType = "RETRIEVAL_DOCUMENT",
    ) -> list[list[float]]:
        """Embed a list of strings, returning one vector per text.

        Processes in batches of _BATCH_SIZE to respect API limits.
        Runs sync SDK in a thread pool so the async event loop stays free.
        """
        all_vectors: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            vectors = await asyncio.to_thread(self._embed_batch, batch, task_type)
            all_vectors.extend(vectors)
        return all_vectors

    def _embed_batch(
        self, texts: list[str], task_type: str
    ) -> list[list[float]]:
        """Synchronous batch embed — called inside asyncio.to_thread."""
        result = genai.embed_content(
            model=self._model,
            content=texts,
            task_type=task_type,
            output_dimensionality=self._embed_dim,
        )
        vectors: list[list[float]] = result["embedding"]
        # Gemini returns a list[list[float]] for batch input.
        # For a single-string input it returns list[float]; normalise.
        if vectors and isinstance(vectors[0], float):
            vectors = [vectors]  # type: ignore[list-item]
        for vec in vectors:
            if len(vec) != self._embed_dim:
                raise ValueError(
                    f"Expected embedding dim {self._embed_dim}, got {len(vec)}. "
                    f"Check Settings.gemini_embed_model and Settings.embed_dim."
                )
        return vectors


@lru_cache(maxsize=1)
def get_embedder(api_key: str, model: str, embed_dim: int) -> GeminiEmbedder:
    """Return the process-wide GeminiEmbedder singleton.

    Cache key is (api_key, model, embed_dim) — changes in settings invalidate
    the cache automatically (lru_cache keyed by args). In practice the cache
    is populated once in lifespan and never invalidated during a process run.
    """
    return GeminiEmbedder(api_key=api_key, model=model, embed_dim=embed_dim)
