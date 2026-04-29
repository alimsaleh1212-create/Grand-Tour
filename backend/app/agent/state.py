"""LangGraph agent state.

Implemented in Stage 5.

The state is the only thing that flows between graph nodes. It is a
TypedDict (LangGraph requirement) but every value is itself a Pydantic
model so we keep typed boundaries inside the graph.

Public surface (planned):
    class AgentState(TypedDict, total=False):
        question: str                         # original user question
        sanitized_question: str               # post _sanitize_query()
        plan: list[ToolStep]                  # tools to fire & in what order
        retrieved: list[SearchHit]            # from retrieve_destinations
        candidates: list[CandidateDestination]# extracted by cheap model
        classifications: list[ClassifyResult] # one per candidate
        live_conditions: list[LiveConditions] # one per top candidate
        final_answer: str                     # from strong model
        token_usage: TokenUsage
        errors: list[ToolErrorReport]         # collected, never raised

    class ToolStep(BaseModel):
        tool_name: str
        args: dict
"""
