"""Chat router — streaming SSE and non-streaming agent entry points.

ENDPOINTS
---------
    POST /chat/stream   — SSE stream; each agent node emits an event as soon
                          as it completes so the user sees partial results
                          immediately (RAG → classify → live → answer).
    POST /chat          — Non-streaming; waits for full agent result then
                          returns ChatResponse.

SSE EVENT TYPES (stream endpoint)
----------------------------------
    {"type":"start",             "question":"..."}
    {"type":"retrieve_result",   "chunks":[...]}
    {"type":"classify_result",   "classifications":[...]}
    {"type":"live_result",       "live_data":[...]}
    {"type":"answer",            "text":"..."}
    {"type":"booking_request",   "flight":{...}}   (Bonus B1)
    {"type":"done",              "run_id":N, "cost_usd":..., "errors":[...]}
    {"type":"error",             "detail":"..."}   (irrecoverable failure)
"""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any, AsyncGenerator

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.settings import get_settings
from app.db.models.agent_run import AgentRun
from app.deps.auth import CurrentUser
from app.deps.db import get_session
from app.schemas.chat import ChatRequest, ChatResponse, ToolFireSummary
from app.services import run_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


# ── helpers ───────────────────────────────────────────────────────────────────


def _sse(event_dict: dict[str, Any]) -> str:
    """Format one SSE frame."""
    return f"data: {json.dumps(event_dict, default=str)}\n\n"


def _serialise_hits(hits: list[Any]) -> list[dict[str, Any]]:
    if not hits:
        return []
    result = []
    for h in hits:
        if hasattr(h, "model_dump"):
            result.append(h.model_dump())
        elif hasattr(h, "__dataclass_fields__"):
            import dataclasses
            result.append(dataclasses.asdict(h))
        else:
            result.append(dict(h))
    return result


def _serialise_list(items: list[Any]) -> list[dict[str, Any]]:
    if not items:
        return []
    result = []
    for item in items:
        if item is None:
            result.append(None)  # type: ignore[arg-type]
        elif hasattr(item, "model_dump"):
            result.append(item.model_dump())
        else:
            result.append(str(item))
    return result


def _serialise_classifications(classifications: list[Any]) -> list[dict[str, Any]]:
    """Normalise ClassifyResult → frontend SseClassification shape.

    Backend uses `predicted_style`; frontend expects `label`.
    """
    out = []
    for c in classifications:
        if c is None:
            continue
        d = c.model_dump() if hasattr(c, "model_dump") else dict(c)
        # Rename predicted_style → label
        if "predicted_style" in d and "label" not in d:
            d["label"] = d.pop("predicted_style")
        out.append(d)
    return out


def _serialise_live(
    raw_features: list[dict[str, Any]], live_data: list[Any]
) -> list[dict[str, Any]]:
    """Normalise LiveConditions → frontend SseLiveConditions shape.

    Adds destination_name (from raw_features) and maps field names:
        WeatherWindow.precipitation_mm  → weather.precip_mm
        WeatherWindow.avg_temp_c        → weather.temp_c
        FlightQuote                     → flights list (price_total → price)
    """
    out = []
    for i, item in enumerate(live_data):
        if item is None:
            continue
        dest_name = raw_features[i].get("destination_name", "") if i < len(raw_features) else ""
        d = item.model_dump() if hasattr(item, "model_dump") else dict(item)

        # Normalise weather sub-object
        w = d.get("weather")
        if w:
            d["weather"] = {
                "temp_c": w.get("avg_temp_c"),
                "min_temp_c": w.get("min_temp_c"),
                "max_temp_c": w.get("max_temp_c"),
                "precip_mm": w.get("precipitation_mm"),
                "description": f"{w.get('avg_temp_c', '?')}°C avg",
            }

        # Normalise flights: FlightQuote → list with schedule details
        fq = d.get("flights")
        if fq:
            d["flights"] = [{
                "origin": fq.get("origin"),
                "origin_city": fq.get("origin_city", ""),
                "destination": fq.get("destination"),
                "destination_city": fq.get("destination_city", ""),
                "destination_airport": fq.get("destination_airport", ""),
                "departure_time": fq.get("departure_time", ""),
                "arrival_time": fq.get("arrival_time", ""),
                "duration_hours": fq.get("duration_hours"),
                "frequency": fq.get("frequency", ""),
                "airline": fq.get("airline", ""),
                "price": fq.get("price_total"),
                "currency": fq.get("currency", "USD"),
                "available": fq.get("available", False),
                "reason": fq.get("reason"),
            }] if fq.get("available") else []

        d["destination_name"] = dest_name
        out.append(d)
    return out


# ── streaming endpoint ────────────────────────────────────────────────────────


@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    request: Request,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StreamingResponse:
    """Stream agent node results as Server-Sent Events.

    The client should use fetch() + ReadableStream (not EventSource, since
    EventSource only supports GET).  Each completed graph node emits one SSE
    frame immediately — the user sees RAG results before the classify node
    even starts.
    """
    agent = request.app.state.agent

    async def _generate() -> AsyncGenerator[str, None]:
        # Create the DB run row
        run: AgentRun = await create_and_commit_run(session, user.id, body.question)
        run_id = run.id

        tokens_cheap = 0
        tokens_strong = 0
        tool_summaries: list[ToolFireSummary] = []
        final_answer = ""
        errors: list[str] = []
        raw_features: list[dict[str, Any]] = []

        try:
            yield _sse({"type": "start", "question": body.question})

            async for update in agent.astream(
                {"question": body.question},
                stream_mode="updates",
            ):
                for node_name, node_output in update.items():
                    if node_name == "retrieve":
                        hits = node_output.get("retrieved_hits") or []
                        yield _sse({
                            "type": "retrieve_result",
                            "chunks": _serialise_hits(hits),
                        })
                        await append_retrieve_call(
                            session, run_id, hits, tool_summaries
                        )

                    elif node_name == "extract":
                        raw_features = node_output.get("raw_features") or []

                    elif node_name == "classify":
                        classifications = node_output.get("classifications") or []
                        yield _sse({
                            "type": "classify_result",
                            "classifications": _serialise_classifications(classifications),
                        })
                        await append_classify_call(
                            session, run_id, classifications, tool_summaries
                        )

                    elif node_name == "live":
                        live_data = node_output.get("live_data") or []
                        yield _sse({
                            "type": "live_result",
                            "live_data": _serialise_live(raw_features, live_data),
                        })
                        await append_live_call(
                            session, run_id, live_data, tool_summaries
                        )

                    elif node_name == "synthesize":
                        text = node_output.get("final_answer") or ""
                        final_answer = text
                        tokens_cheap += node_output.get("tokens_in", 0) or 0
                        tokens_strong += node_output.get("tokens_out", 0) or 0
                        yield _sse({"type": "answer", "text": text})

                    elif node_name in ("sanitize", "extract"):
                        # accumulate token counts from intermediate nodes
                        tokens_cheap += node_output.get("tokens_in", 0) or 0

                    # collect errors from any node
                    node_errors = node_output.get("errors") or []
                    errors.extend(node_errors)

            # Finalise in DB
            run = await run_service.finalise_run(
                session,
                run_id=run_id,
                final_answer=final_answer,
                total_tokens_cheap=tokens_cheap,
                total_tokens_strong=tokens_strong,
                webhook_status=None,
            )
            await session.commit()

            yield _sse({
                "type": "done",
                "run_id": run_id,
                "cost_usd": float(run.cost_usd),
                "errors": errors,
            })

            # Signal frontend that Discord notification is available
            if get_settings().discord_webhook_url:
                yield _sse({"type": "webhook_available", "run_id": run_id})

        except Exception as exc:
            log.error("chat.stream.error", exc_info=True)
            yield _sse({"type": "error", "detail": "Agent processing failed."})
            try:
                await session.rollback()
            except Exception:
                pass

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── non-streaming endpoint ────────────────────────────────────────────────────


@router.post("", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat(
    body: ChatRequest,
    request: Request,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChatResponse:
    """Run the full agent and return a single ChatResponse when done.

    Useful for programmatic API clients that don't need streaming.
    """
    agent = request.app.state.agent

    run: AgentRun = await create_and_commit_run(session, user.id, body.question)
    run_id = run.id

    tool_summaries: list[ToolFireSummary] = []
    tokens_cheap = 0
    tokens_strong = 0

    final_state = await agent.ainvoke({"question": body.question})

    # Record tool calls from final state
    for classification in final_state.get("classifications") or []:
        tool_summaries.append(ToolFireSummary(
            tool_name="classify_style", ok=True, latency_ms=0
        ))
    if final_state.get("retrieved_hits"):
        tool_summaries.insert(0, ToolFireSummary(
            tool_name="retrieve_destinations", ok=True, latency_ms=0
        ))
    if final_state.get("live_data"):
        tool_summaries.append(ToolFireSummary(
            tool_name="live_conditions", ok=True, latency_ms=0
        ))

    tokens_cheap = final_state.get("tokens_in", 0) or 0
    tokens_strong = final_state.get("tokens_out", 0) or 0
    final_answer = final_state.get("final_answer", "") or ""

    run = await run_service.finalise_run(
        session,
        run_id=run_id,
        final_answer=final_answer,
        total_tokens_cheap=tokens_cheap,
        total_tokens_strong=tokens_strong,
        webhook_status=None,
    )
    await session.commit()

    return ChatResponse(
        run_id=run_id,
        answer=final_answer,
        tools_fired=tool_summaries,
        cost_usd=float(run.cost_usd),
        tokens_cheap=tokens_cheap,
        tokens_strong=tokens_strong,
    )


# ── helpers ────────────────────────────────────────────────────────────────────


async def create_and_commit_run(
    session: AsyncSession, user_id: int, question: str
) -> AgentRun:
    run = await run_service.create_run(session, user_id=user_id, question=question)
    await session.commit()
    await session.refresh(run)
    return run


async def append_retrieve_call(
    session: AsyncSession,
    run_id: int,
    hits: list[Any],
    summaries: list[ToolFireSummary],
) -> None:
    serialised = _serialise_hits(hits)
    await run_service.append_tool_call(
        session,
        run_id=run_id,
        tool_name="retrieve_destinations",
        args={"top_k": len(hits)},
        result={"chunks": serialised},
        tokens=0,
        latency_ms=0,
        error=None,
    )
    await session.commit()
    summaries.append(ToolFireSummary(
        tool_name="retrieve_destinations", ok=True, latency_ms=0
    ))


async def append_classify_call(
    session: AsyncSession,
    run_id: int,
    classifications: list[Any],
    summaries: list[ToolFireSummary],
) -> None:
    serialised = _serialise_list(classifications)
    await run_service.append_tool_call(
        session,
        run_id=run_id,
        tool_name="classify_style",
        args={},
        result={"classifications": serialised},
        tokens=0,
        latency_ms=0,
        error=None,
    )
    await session.commit()
    summaries.append(ToolFireSummary(
        tool_name="classify_style", ok=True, latency_ms=0
    ))


async def append_live_call(
    session: AsyncSession,
    run_id: int,
    live_data: list[Any],
    summaries: list[ToolFireSummary],
) -> None:
    serialised = _serialise_list(live_data)
    await run_service.append_tool_call(
        session,
        run_id=run_id,
        tool_name="live_conditions",
        args={},
        result={"live_data": serialised},
        tokens=0,
        latency_ms=0,
        error=None,
    )
    await session.commit()
    summaries.append(ToolFireSummary(
        tool_name="live_conditions", ok=True, latency_ms=0
    ))
