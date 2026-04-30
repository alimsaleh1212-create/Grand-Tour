"""AgentRun lifecycle service — create, update, and query agent runs.

PUBLIC SURFACE
--------------
    async def create_run(session, *, user_id, question) -> AgentRun
    async def append_tool_call(session, *, run_id, tool_name, args,
                               result, tokens, latency_ms, error) -> ToolCall
    async def finalise_run(session, *, run_id, final_answer,
                           total_tokens_cheap, total_tokens_strong,
                           cost_usd) -> AgentRun
    async def list_runs_for_user(session, *, user_id, limit) -> list[AgentRun]
    async def get_run_for_user(session, *, user_id, run_id) -> AgentRun | None
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.agent_run import AgentRun
from app.db.models.tool_call import ToolCall

log = logging.getLogger(__name__)

# Gemini pricing as of 2025 (USD per 1 000 tokens, approximate)
_FLASH_INPUT_PER_1K = Decimal("0.000075")
_FLASH_OUTPUT_PER_1K = Decimal("0.0003")
_PRO_INPUT_PER_1K = Decimal("0.00125")
_PRO_OUTPUT_PER_1K = Decimal("0.005")


def _estimate_cost(
    tokens_cheap: int,
    tokens_strong: int,
) -> Decimal:
    """Rough Gemini cost estimate from token counts.

    Assumes cheap tokens split 60/40 input/output and strong are all
    synthesis output (1 call per request).  Good enough for README reporting.
    """
    cheap_in = Decimal(tokens_cheap) * Decimal("0.6") / 1000
    cheap_out = Decimal(tokens_cheap) * Decimal("0.4") / 1000
    strong_in = Decimal(tokens_strong) * Decimal("0.3") / 1000
    strong_out = Decimal(tokens_strong) * Decimal("0.7") / 1000

    return (
        cheap_in * _FLASH_INPUT_PER_1K
        + cheap_out * _FLASH_OUTPUT_PER_1K
        + strong_in * _PRO_INPUT_PER_1K
        + strong_out * _PRO_OUTPUT_PER_1K
    ).quantize(Decimal("0.000001"))


async def create_run(
    session: AsyncSession,
    *,
    user_id: int,
    question: str,
) -> AgentRun:
    """Insert a new AgentRun row with started_at = now.

    Args:
        session: Open AsyncSession.
        user_id: FK to users.id.
        question: Original user question.

    Returns:
        The persisted AgentRun instance.
    """
    run = AgentRun(
        user_id=user_id,
        question=question,
        started_at=datetime.now(timezone.utc),
    )
    session.add(run)
    await session.flush()  # populate run.id without committing the transaction
    log.info("run.created", extra={"run_id": run.id, "user_id": user_id})
    return run


async def append_tool_call(
    session: AsyncSession,
    *,
    run_id: int,
    tool_name: str,
    args: dict[str, Any],
    result: dict[str, Any] | None,
    tokens: int,
    latency_ms: int,
    error: str | None,
) -> ToolCall:
    """Insert one ToolCall row for a completed tool invocation.

    Args:
        session: Open AsyncSession.
        run_id: FK to agent_runs.id.
        tool_name: BaseTool.name value.
        args: Serialised input dict.
        result: Serialised output dict (or None on failure).
        tokens: Token count for the cheap-model call that produced these args.
        latency_ms: Wall-clock duration of safe_run().
        error: Sanitised error string (or None on success).

    Returns:
        The persisted ToolCall instance.
    """
    call = ToolCall(
        run_id=run_id,
        tool_name=tool_name,
        args_json=args,
        result_json=result,
        tokens=tokens,
        latency_ms=latency_ms,
        error=error,
    )
    session.add(call)
    await session.flush()
    return call


async def finalise_run(
    session: AsyncSession,
    *,
    run_id: int,
    final_answer: str,
    total_tokens_cheap: int,
    total_tokens_strong: int,
    webhook_status: str | None = None,
) -> AgentRun:
    """Set final_answer, token totals, cost, and finished_at on the run.

    Args:
        session: Open AsyncSession.
        run_id: PK of the AgentRun to update.
        final_answer: Agent synthesis output.
        total_tokens_cheap: Cumulative Flash tokens across all tool calls.
        total_tokens_strong: Cumulative Pro tokens (synthesis only).
        webhook_status: "pending" | "delivered" | "failed" | None.

    Returns:
        The updated AgentRun instance.
    """
    result = await session.execute(
        select(AgentRun).where(AgentRun.id == run_id)
    )
    run = result.scalar_one()
    run.final_answer = final_answer
    run.total_tokens_cheap = total_tokens_cheap
    run.total_tokens_strong = total_tokens_strong
    run.cost_usd = _estimate_cost(total_tokens_cheap, total_tokens_strong)
    run.finished_at = datetime.now(timezone.utc)
    if webhook_status is not None:
        run.webhook_status = webhook_status
    await session.flush()

    log.info(
        "run.finalised",
        extra={
            "run_id": run_id,
            "cost_usd": str(run.cost_usd),
            "tokens_cheap": total_tokens_cheap,
            "tokens_strong": total_tokens_strong,
        },
    )
    return run


async def list_runs_for_user(
    session: AsyncSession,
    *,
    user_id: int,
    limit: int = 50,
) -> list[AgentRun]:
    """Return the user's most recent AgentRun rows (no tool_calls loaded).

    Args:
        session: Open AsyncSession.
        user_id: Filter — only runs belonging to this user.
        limit: Maximum number of rows to return.

    Returns:
        List of AgentRun ordered by started_at descending.
    """
    stmt = (
        select(AgentRun)
        .where(AgentRun.user_id == user_id)
        .order_by(AgentRun.started_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_run_for_user(
    session: AsyncSession,
    *,
    user_id: int,
    run_id: int,
) -> AgentRun | None:
    """Return one AgentRun with eager-loaded tool_calls, or None.

    Returns None (not NotFoundError) when:
        - The run_id does not exist.
        - The run belongs to a different user (cross-user isolation).
    The router converts None → 404 so both cases look identical to the client.

    Args:
        session: Open AsyncSession.
        user_id: The authenticated user's id.
        run_id: PK of the requested run.

    Returns:
        AgentRun with tool_calls loaded, or None.
    """
    stmt = (
        select(AgentRun)
        .where(AgentRun.id == run_id, AgentRun.user_id == user_id)
        .options(selectinload(AgentRun.tool_calls))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
