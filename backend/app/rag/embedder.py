"""Async embedding client — local Ollama (`nomic-embed-text`, 768-dim).

Implemented in Stage 4.

Design:
    * `httpx.AsyncClient` constructed once per process (lifespan singleton),
      cached via `lru_cache` so repeated `get_embedder()` calls reuse the
      connection pool.
    * Batched API: `embed_texts(list[str])` issues a single Ollama request
      (or a tight loop where Ollama lacks true batching — wrapped to look
      batched). NEVER one-call-per-chunk in a Python list comp.
    * Tenacity retry on connection / 5xx errors with exponential backoff.
    * `assert len(vec) == EMBED_DIM` so a config drift surfaces immediately.

Public surface (planned):
    class OllamaEmbedder:
        def __init__(self, host: str, model: str, expected_dim: int,
                     client: httpx.AsyncClient): ...
        async def embed_text(self, text: str) -> list[float]: ...
        async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

    @lru_cache(maxsize=1)
    def get_embedder() -> OllamaEmbedder: ...
"""
