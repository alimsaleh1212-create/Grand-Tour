"""Chat request/response schemas and SSE event models.

PUBLIC SURFACE
--------------
    class ChatRequest(BaseModel)         — POST /chat body
    class ChatResponse(BaseModel)        — POST /chat (non-streaming) response
    class ToolFireSummary(BaseModel)     — one row in tools_fired list
    class RunOut(BaseModel)              — GET /runs list item
    class RunDetailOut(BaseModel)        — GET /runs/{id} with tool calls
    class ToolCallOut(BaseModel)         — one tool call in the timeline
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    """Body for POST /chat and POST /chat/stream."""

    question: str = Field(..., min_length=1, max_length=2000)
    webhook_url: str | None = Field(
        default=None,
        description="Optional URL to POST the final answer to when done.",
    )


class ToolFireSummary(BaseModel):
    """Summary of one tool invocation, returned in ChatResponse."""

    tool_name: str
    ok: bool
    latency_ms: int
    error: str | None = None


class ChatResponse(BaseModel):
    """Non-streaming POST /chat response — returned after agent finishes."""

    run_id: int
    answer: str
    tools_fired: list[ToolFireSummary]
    cost_usd: float
    tokens_cheap: int
    tokens_strong: int


class ToolCallOut(BaseModel):
    """One ToolCall row for the RunDetail timeline."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tool_name: str
    args_json: dict[str, Any]
    result_json: dict[str, Any] | None
    tokens: int
    latency_ms: int
    error: str | None
    created_at: datetime


class RunOut(BaseModel):
    """Light representation used in GET /runs list."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    final_answer: str | None
    cost_usd: Decimal
    started_at: datetime
    finished_at: datetime | None


class RunDetailOut(BaseModel):
    """Full AgentRun detail with embedded tool calls, for GET /runs/{id}."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    final_answer: str | None
    total_tokens_cheap: int
    total_tokens_strong: int
    cost_usd: Decimal
    webhook_status: str | None
    started_at: datetime
    finished_at: datetime | None
    tool_calls: list[ToolCallOut]
