"""Tool 1 — retrieve_destinations (RAG over pgvector).

Implemented in Stage 5 (after Stage 4 ingestion is done).

Schemas (planned):
    class RetrieveQuery(BaseModel):
        query_text: str = Field(min_length=3, max_length=500)
        top_k: int = Field(default=5, ge=1, le=20)

    class RetrievedChunk(BaseModel):
        source: str
        chunk_index: int
        text: str
        distance: float

    class RetrieveResult(BaseModel):
        query: str
        chunks: list[RetrievedChunk]

Class (planned):
    class RetrieveDestinationsTool(BaseTool[RetrieveQuery, RetrieveResult]):
        name = "retrieve_destinations"
        input_schema = RetrieveQuery
        output_schema = RetrieveResult

        def __init__(self, embedder: OllamaEmbedder, store: VectorStore): ...

        async def run(self, args: RetrieveQuery) -> RetrieveResult:
            vector = await self.embedder.embed_text(args.query_text)
            hits = await self.store.search(vector, args.top_k)
            return RetrieveResult(query=args.query_text, chunks=...)

Notes:
    * The embedder + store are injected — the tool itself never builds
      clients. Lifecycle is owned by the lifespan handler.
"""
