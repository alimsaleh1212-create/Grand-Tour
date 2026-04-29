"""Async embedding client — Google Gemini gemini-embedding-001 (768-dim).

WHY DIRECT REST INSTEAD OF THE SDK
------------------------------------
Both `google-generativeai` and `google-genai` SDK versions route calls through
v1beta endpoints in ways that don't always match the model's supported methods.
We call the REST API directly via httpx (already a project dependency) to stay
explicit about the URL, API version, and payload shape.

MODEL CHOICE
------------
`models/gemini-embedding-001` is the stable 768-dim Gemini embedding model
available in the project's Google AI Studio API key.  `text-embedding-004`
(an earlier alias) is not available on this key.  Both produce 768-dim vectors
that match the pgvector column dimension.

WHY NOT batchEmbedContents
----------------------------
The model only supports `embedContent` (single-text call).  For parallelism we
fire up to _MAX_CONCURRENT requests concurrently using asyncio.gather — this is
faster than a serial loop and avoids blocking the event loop (pure async httpx).

TASK TYPES
----------
    RETRIEVAL_DOCUMENT  — ingest time (knowledge chunks stored in pgvector)
    RETRIEVAL_QUERY     — query time (user question before similarity search)
Callers must pass the right type; the embedder does not infer it.

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

import httpx

TaskType = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY", "SEMANTIC_SIMILARITY"]

_MAX_CONCURRENT = 20  # concurrent embedContent requests
_EMBED_URL = (
    "https://generativelanguage.googleapis.com/v1beta/{model}:embedContent"
)


class GeminiEmbedder:
    """Fully async Gemini embedding client using concurrent REST calls.

    Uses an httpx.AsyncClient with a connection pool so concurrent requests
    reuse the same TCP connections rather than opening a new one per call.
    """

    def __init__(self, *, api_key: str, model: str, embed_dim: int) -> None:
        self._api_key = api_key
        # Normalize: the REST path needs the "models/" prefix.
        self._model = model if model.startswith("models/") else f"models/{model}"
        self._embed_dim = embed_dim
        self._url = _EMBED_URL.format(model=self._model)
        # Shared async client — connection pool reused across all concurrent calls.
        self._http = httpx.AsyncClient(timeout=60.0)

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
        """Embed a list of strings concurrently, returning one vector per text.

        Fires up to _MAX_CONCURRENT requests at once via asyncio.gather.
        """
        semaphore = asyncio.Semaphore(_MAX_CONCURRENT)

        async def _one(text: str) -> list[float]:
            async with semaphore:
                return await self._embed_one(text, task_type)

        return list(await asyncio.gather(*[_one(t) for t in texts]))

    async def _embed_one(self, text: str, task_type: str) -> list[float]:
        """POST embedContent for a single text; validate dimension."""
        payload = {
            "model": self._model,
            "content": {"parts": [{"text": text}]},
            "taskType": task_type,
            "outputDimensionality": self._embed_dim,
        }
        response = await self._http.post(
            self._url,
            params={"key": self._api_key},
            json=payload,
        )
        response.raise_for_status()
        vec: list[float] = response.json()["embedding"]["values"]
        if len(vec) != self._embed_dim:
            raise ValueError(
                f"Expected embedding dim {self._embed_dim}, got {len(vec)}. "
                f"Check Settings.gemini_embed_model and Settings.embed_dim."
            )
        return vec

    async def aclose(self) -> None:
        """Close the shared HTTP client (call on shutdown)."""
        await self._http.aclose()


@lru_cache(maxsize=1)
def get_embedder(api_key: str, model: str, embed_dim: int) -> GeminiEmbedder:
    """Return the process-wide GeminiEmbedder singleton.

    Cache key is (api_key, model, embed_dim) — settings changes invalidate
    automatically. Populated once in lifespan; never re-created per request.
    """
    return GeminiEmbedder(api_key=api_key, model=model, embed_dim=embed_dim)
