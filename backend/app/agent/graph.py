"""LangGraph state machine — the compiled travel-planning agent.

TOPOLOGY
--------
    START
      ▼
    sanitize_node      — wrap user input, log suspicious patterns
      ▼
    retrieve_node      — embed query → pgvector cosine search
      ▼
    extract_node       — cheap LLM extracts DestinationFeatures from chunks
      ▼
    classify_node      — fan-out classify_style for each candidate
      ▼
    live_node          — fan-out live_conditions for each classified candidate
      ▼
    synthesize_node    — STRONG LLM writes the final answer (fires once)
      ▼
    END

Cost note: the strong model fires EXACTLY ONCE per query (synthesis).  All
other LLM calls use the cheap (Flash) tier.

PUBLIC SURFACE
--------------
    @dataclass
    class AgentDeps:
        cheap_llm: GeminiClient
        strong_llm: GeminiClient
        retriever: RetrieveDestinationsTool
        classifier: ClassifyStyleTool
        live_tool: LiveConditionsTool

    def build_agent(deps: AgentDeps) -> CompiledGraph
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from langgraph.graph import END, StateGraph

from app.agent.llm_clients import GeminiClient
from app.agent.prompts import (
    SYSTEM_FEATURE_EXTRACTOR,
    SYSTEM_FINAL_SYNTHESIS,
    build_feature_extractor_prompt,
    build_synthesis_prompt,
)
from app.agent.security import sanitize_query
from app.agent.state import AgentState
from app.agent.tools.classify_style import ClassifyInput, ClassifyStyleTool, DestinationFeatures
from app.agent.tools.live_conditions import LiveConditionsTool, LiveConditionsQuery
from app.agent.tools.retrieve_destinations import RetrieveDestinationsTool, RetrieveQuery

log = logging.getLogger(__name__)

# Top-N candidates to pass to live_conditions (avoids hammering weather/FX APIs)
_MAX_LIVE_CANDIDATES = 3


@dataclass
class AgentDeps:
    """All singletons injected into the agent at construction time.

    Built once in the FastAPI lifespan and passed to build_agent().  Tests
    inject fakes via this dataclass — no monkey-patching required.
    """

    cheap_llm: GeminiClient
    strong_llm: GeminiClient
    retriever: RetrieveDestinationsTool
    classifier: ClassifyStyleTool
    live_tool: LiveConditionsTool


def build_agent(deps: AgentDeps) -> Any:
    """Compile and return the LangGraph state machine.

    Args:
        deps: Injected singletons for each node that needs external I/O.

    Returns:
        CompiledGraph ready for ainvoke({"question": "..."}).
    """
    graph: StateGraph = StateGraph(AgentState)

    # ── Node definitions ───────────────────────────────────────────────────────

    async def sanitize_node(state: AgentState) -> dict[str, Any]:
        question: str = state.get("question", "")
        sanitized = sanitize_query(question)
        log.info("agent.sanitize", extra={"original_len": len(question)})
        return {
            "sanitized_question": sanitized,
            "tokens_in": 0,
            "tokens_out": 0,
            "errors": [],
        }

    async def retrieve_node(state: AgentState) -> dict[str, Any]:
        question = state.get("sanitized_question", "")
        result = await deps.retriever.safe_run(
            {"query_text": question, "top_k": 5}
        )
        errors: list[str] = list(state.get("errors") or [])
        if not result.ok or result.output is None:
            errors.append(f"retrieve_destinations: {result.error}")
            log.warning("agent.retrieve.failed", extra={"error": result.error})
            return {"retrieved_hits": [], "errors": errors}

        hits = result.output.chunks
        log.info(
            "agent.retrieve.success",
            extra={"hits": len(hits)},
        )
        return {"retrieved_hits": hits, "errors": errors}

    async def extract_node(state: AgentState) -> dict[str, Any]:
        """Cheap LLM extracts DestinationFeatures list from retrieved chunks."""
        hits = state.get("retrieved_hits") or []
        question = state.get("sanitized_question", "")
        tokens_in: int = state.get("tokens_in") or 0
        tokens_out: int = state.get("tokens_out") or 0
        errors: list[str] = list(state.get("errors") or [])

        if not hits:
            return {"raw_features": [], "tokens_in": tokens_in, "tokens_out": tokens_out}

        user_prompt = build_feature_extractor_prompt(question, hits)
        generation = await deps.cheap_llm.generate(
            system_prompt=SYSTEM_FEATURE_EXTRACTOR,
            user_prompt=user_prompt,
            json_mode=True,
        )
        tokens_in += generation.tokens_in
        tokens_out += generation.tokens_out

        raw_features: list[dict[str, Any]] = []
        try:
            # Strip markdown code fences if the LLM wraps output
            text = generation.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
                text = text.rsplit("```", 1)[0]
            parsed = json.loads(text)
            if isinstance(parsed, list):
                raw_features = parsed
            elif isinstance(parsed, dict):
                raw_features = [parsed]
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(f"extract_node JSON parse failed: {exc}")
            log.warning("agent.extract.parse_failed", extra={"error": str(exc)})

        log.info(
            "agent.extract.success",
            extra={"candidates": len(raw_features)},
        )
        return {
            "raw_features": raw_features,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "errors": errors,
        }

    async def classify_node(state: AgentState) -> dict[str, Any]:
        """Fan-out classify_style for each extracted candidate."""
        raw_features: list[dict[str, Any]] = list(state.get("raw_features") or [])
        tokens_in: int = state.get("tokens_in") or 0
        tokens_out: int = state.get("tokens_out") or 0
        errors: list[str] = list(state.get("errors") or [])

        async def _classify_one(feat_dict: dict[str, Any]) -> Any:
            dest_name: str = str(feat_dict.get("destination_name", "Unknown"))
            # Build the ClassifyInput, merging feature fields
            classify_args = {
                "destination_name": dest_name,
                "features": {k: v for k, v in feat_dict.items() if k != "destination_name"},
            }
            result = await deps.classifier.safe_run(classify_args)
            if not result.ok or result.output is None:
                errors.append(f"classify_style({dest_name}): {result.error}")
                log.warning(
                    "agent.classify.failed",
                    extra={"destination": dest_name, "error": result.error},
                )
                return None
            return result.output

        tasks = [_classify_one(f) for f in raw_features]
        results = await asyncio.gather(*tasks)
        classifications = [r for r in results if r is not None]

        log.info(
            "agent.classify.success",
            extra={"classified": len(classifications)},
        )
        return {
            "classifications": classifications,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "errors": errors,
        }

    async def live_node(state: AgentState) -> dict[str, Any]:
        """Fan-out live_conditions for the top-N classified candidates."""
        raw_features: list[dict[str, Any]] = list(state.get("raw_features") or [])
        classifications = list(state.get("classifications") or [])
        errors: list[str] = list(state.get("errors") or [])

        # Only query live data for the top _MAX_LIVE_CANDIDATES
        candidates = raw_features[:_MAX_LIVE_CANDIDATES]

        today = date.today()
        # Open-Meteo forecast max = 16 days; use next 7 days for live conditions
        trip_start = today + timedelta(days=1)
        trip_end = today + timedelta(days=7)

        async def _live_one(feat_dict: dict[str, Any]) -> Any:
            dest_name: str = str(feat_dict.get("destination_name", ""))
            lat = float(feat_dict.get("latitude", 0) or 0)
            lon = float(feat_dict.get("longitude", 0) or 0)
            currency = str(feat_dict.get("currency_code", "USD") or "USD")

            args = {
                "city": dest_name,
                "latitude": lat,
                "longitude": lon,
                "date_from": trip_start.isoformat(),
                "date_to": trip_end.isoformat(),
                "base_currency": "USD",
                "quote_currency": currency if currency != "USD" else "USD",
            }
            result = await deps.live_tool.safe_run(args)
            if not result.ok or result.output is None:
                errors.append(f"live_conditions({dest_name}): {result.error}")
                log.warning(
                    "agent.live.failed",
                    extra={"destination": dest_name, "error": result.error},
                )
                return None
            return result.output

        tasks = [_live_one(f) for f in candidates]
        live_data = list(await asyncio.gather(*tasks))

        # Pad to match classifications length if shorter
        while len(live_data) < len(classifications):
            live_data.append(None)

        log.info(
            "agent.live.success",
            extra={"live_fetched": sum(1 for d in live_data if d is not None)},
        )
        return {"live_data": live_data, "errors": errors}

    async def synthesize_node(state: AgentState) -> dict[str, Any]:
        """Strong LLM writes the final travel recommendation."""
        tokens_in: int = state.get("tokens_in") or 0
        tokens_out: int = state.get("tokens_out") or 0

        user_prompt = build_synthesis_prompt(state)
        generation = await deps.strong_llm.generate(
            system_prompt=SYSTEM_FINAL_SYNTHESIS,
            user_prompt=user_prompt,
        )
        tokens_in += generation.tokens_in
        tokens_out += generation.tokens_out

        log.info(
            "agent.synthesize.success",
            extra={"tokens_in": tokens_in, "tokens_out": tokens_out},
        )
        return {
            "final_answer": generation.text,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }

    # ── Graph wiring ───────────────────────────────────────────────────────────

    graph.add_node("sanitize", sanitize_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("extract", extract_node)
    graph.add_node("classify", classify_node)
    graph.add_node("live", live_node)
    graph.add_node("synthesize", synthesize_node)

    graph.set_entry_point("sanitize")
    graph.add_edge("sanitize", "retrieve")
    graph.add_edge("retrieve", "extract")
    graph.add_edge("extract", "classify")
    graph.add_edge("classify", "live")
    graph.add_edge("live", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()
