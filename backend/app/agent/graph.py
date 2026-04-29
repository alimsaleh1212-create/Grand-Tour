"""LangGraph state machine — the compiled agent.

Implemented in Stage 5.

Topology (planned):

    START
      ▼
    sanitize_node       wrap user input, log suspicious patterns
      ▼
    plan_node           cheap LLM picks tool sequence (allowlist enforced)
      ▼
    tool_loop_node ──── for each step: validate args → safe_run → record
      ▼
    extract_candidates  cheap LLM pulls structured candidates from
                        retrieved chunks (Pydantic schema)
      ▼
    classify_node       fan-out classify_style for each candidate
      ▼
    live_node           fan-out live_conditions for top candidates
      ▼
    synthesise_node     STRONG LLM writes the final answer using all
                        accumulated state
      ▼
    persist_node        write tool_calls + finalise AgentRun
      ▼
    END

Cost note: the strong model fires exactly ONCE per query (the synthesis
step). Everything else is on the cheap tier.

Public surface (planned):
    def build_agent(*, deps: AgentDeps) -> CompiledGraph: ...

    @dataclass
    class AgentDeps:
        cheap_llm: GeminiClient
        strong_llm: GeminiClient
        embedder: OllamaEmbedder
        vector_store: VectorStore
        classifier: Pipeline
        live_client: httpx.AsyncClient
        sessionmaker: async_sessionmaker[AsyncSession]
"""
