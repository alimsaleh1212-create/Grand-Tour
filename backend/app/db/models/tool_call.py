"""ToolCall ORM model — one row per tool invocation inside an AgentRun.

HOW THIS MODEL FITS INTO THE DATA FLOW
----------------------------------------
    Agent graph (Stage 5) — tool-loop node
        → calls BaseTool.safe_run(raw_args)
        → records start_time = time.monotonic()
        → tool completes (or fails with structured ToolResult{ok=False})
        → latency_ms = int((time.monotonic() - start_time) * 1000)
        → run_service.record_tool_call(
              run_id, tool_name, args, result, tokens, latency_ms, error
          )
        → ToolCall row inserted

    GET /runs/{id}  (Stage 6)
        → fetch AgentRun with eager-loaded tool_calls
        → serialise tool_calls as a timeline for the RunDetail page

WHY JSONB NOT TEXT
-------------------
Storing `args_json` and `result_json` as JSONB (not TEXT) means:
    * Postgres can index specific JSON keys in the future.
    * The DB validates that the value is well-formed JSON on INSERT.
    * Queries like `WHERE args_json->>'city' = 'Tokyo'` work without
      full-table text matching.
SQLAlchemy's `JSON` type maps to JSONB when using asyncpg.

WHY error IS A STRING NOT A BOOLEAN
-------------------------------------
A boolean `ok` flag would be less useful for debugging.  A short string
(e.g. "timeout after 5.0s" or "ValidationError: field 'city' required")
lets us aggregate failures by type without joining another table.  The
string is sanitised before storage (no stack traces, no user data).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.agent_run import AgentRun


class ToolCall(TimestampMixin, Base):
    """One row per tool invocation — the detailed audit log.

    Columns
    -------
    id          : surrogate PK
    run_id      : FK → agent_runs.id (indexed for per-run list queries)
    tool_name   : one of {retrieve_destinations, classify_style,
                  live_conditions} — the BaseTool.name value
    args_json   : the Pydantic input model serialised as a dict
    result_json : the structured ToolResult (ok, data, error)
    tokens      : tokens consumed by the cheap model to produce these args
    latency_ms  : wall-clock duration of BaseTool.safe_run()
    error       : sanitised error message when ok=False, NULL on success
    """

    __tablename__ = "tool_calls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    run_id: Mapped[int] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)

    args_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Many-to-one: this tool call belongs to one run.
    run: Mapped[AgentRun] = relationship("AgentRun", back_populates="tool_calls")
