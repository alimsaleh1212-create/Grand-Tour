"""LangGraph agent state — the only thing that flows between graph nodes.

Every node receives the full AgentState and returns a partial dict of the
fields it modified.  LangGraph merges these partials automatically.

Imports from tool/store modules are deferred under TYPE_CHECKING to avoid
circular imports — at runtime, type hints are strings (PEP 563).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from app.agent.tools.classify_style import ClassifyResult
    from app.agent.tools.live_conditions import LiveConditions
    from app.rag.store import SearchHit


class AgentState(TypedDict, total=False):
    """Mutable state that flows between LangGraph nodes.

    Fields are populated sequentially by each node; earlier nodes set the
    values that later nodes read.  All fields are optional (total=False) so
    nodes can return only the fields they updated.

    Fields:
        question: Original user question (raw, pre-sanitization).
        sanitized_question: Output of security.sanitize_query().
        retrieved_hits: SearchHit list from retrieve_destinations tool.
        raw_features: List of dicts, one per candidate destination, produced
            by the cheap LLM extracting structured features from retrieved
            chunks. Each dict matches the DestinationFeatures field names.
        classifications: ClassifyResult list, one per candidate.
        live_data: LiveConditions (or None) for top candidates.
        final_answer: Markdown string from the strong Gemini model.
        tokens_in: Cumulative prompt tokens across all LLM calls.
        tokens_out: Cumulative completion tokens across all LLM calls.
        errors: Accumulated non-fatal error strings from safe_run() failures.
    """

    question: str
    sanitized_question: str
    retrieved_hits: list[Any]       # list[SearchHit] at runtime
    raw_features: list[dict[str, Any]]
    classifications: list[Any]      # list[ClassifyResult] at runtime
    live_data: list[Any]            # list[LiveConditions | None] at runtime
    final_answer: str
    tokens_in: int
    tokens_out: int
    errors: list[str]
