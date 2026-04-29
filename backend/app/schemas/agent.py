"""Read-side projections of agent runs and tool calls.

Implemented in Stage 6 (alongside /runs router).

Public surface (planned):
    class ToolCallOut(BaseModel):
        id: int
        tool_name: str
        args: dict
        result: dict | None
        tokens: int
        latency_ms: int
        error: str | None
        created_at: datetime
        model_config = ConfigDict(from_attributes=True)

    class AgentRunOut(BaseModel):
        id: int
        question: str
        final_answer: str | None
        total_tokens_cheap: int
        total_tokens_strong: int
        cost_usd: float
        webhook_status: str | None
        started_at: datetime
        finished_at: datetime | None
        tool_calls: list[ToolCallOut]
        model_config = ConfigDict(from_attributes=True)
"""
