"""Chat request/response schemas — the agent's HTTP entry point.

Implemented in Stage 6.

Public surface (planned):
    class ChatRequest(BaseModel):
        question: str = Field(min_length=1, max_length=2000)
        webhook_url: HttpUrl | None = None

    class ToolFireSummary(BaseModel):
        tool_name: str
        ok: bool
        latency_ms: int

    class ChatResponse(BaseModel):
        run_id: int
        answer: str
        tools_fired: list[ToolFireSummary]
        cost_usd: float
"""
