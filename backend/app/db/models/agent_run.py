"""AgentRun ORM model — header row for one agent invocation.

HOW THIS MODEL FITS INTO THE DATA FLOW
----------------------------------------
    POST /chat  (Stage 6)
        → run_service.create_run(user_id, question)
        → AgentRun row inserted (final_answer=None, started_at=now)
        → agent executes (tools fire, ToolCall rows inserted per tool)
        → run_service.complete_run(run_id, answer, tokens, cost)
        → AgentRun.final_answer, .finished_at, .total_tokens_*, .cost_usd set

    GET /runs            → list AgentRun WHERE user_id = current_user.id
    GET /runs/{id}       → fetch AgentRun + eager-load tool_calls

WHY TWO TOKEN COUNTERS
-----------------------
The agent uses two Gemini models:
    * cheap  — gemini-2.5-flash  — routing, extraction, arg generation
    * strong — gemini-2.5-pro    — final synthesis only

Tracking them separately lets us report per-model costs accurately, which
the project brief requires in the cost-breakdown README section.

WHY webhook_status IS A STRING NOT AN ENUM
-------------------------------------------
A Python Enum would require an Alembic migration every time we add a new
status.  A plain string column with an application-level constraint (or a
Postgres CHECK constraint added later) is more pragmatic here.  The values
are: NULL (webhook not requested), "pending", "delivered", "failed".

WHY cost_usd IS NUMERIC NOT FLOAT
-----------------------------------
Financial values must not be stored as IEEE 754 floats — the representation
error compounds over many rows and produces wrong aggregates.  NUMERIC(10, 6)
gives microsecond-USD precision while fitting Postgres's exact arithmetic.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.tool_call import ToolCall
    from app.db.models.user import User


class AgentRun(TimestampMixin, Base):
    """One row per agent invocation — the header of the audit trail.

    Columns
    -------
    id                   : surrogate PK
    user_id              : FK → users.id (indexed for per-user list queries)
    question             : original user text, stored verbatim for audit
    final_answer         : agent synthesis output, NULL until agent finishes
    total_tokens_cheap   : cumulative Gemini Flash token usage across all tool
                           calls in this run
    total_tokens_strong  : cumulative Gemini Pro token usage (synthesis only)
    cost_usd             : computed at run completion from token counts and
                           published Gemini pricing
    webhook_status       : NULL | "pending" | "delivered" | "failed"
    started_at           : set when the run row is first created
    finished_at          : set by complete_run() after synthesis returns
    """

    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    question: Mapped[str] = mapped_column(Text, nullable=False)

    final_answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    total_tokens_cheap: Mapped[int] = mapped_column(default=0, nullable=False)
    total_tokens_strong: Mapped[int] = mapped_column(default=0, nullable=False)

    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6),
        default=Decimal("0"),
        nullable=False,
    )

    webhook_status: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        default=None,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Many-to-one: this run belongs to one user.
    user: Mapped[User] = relationship("User", back_populates="runs")

    # One-to-many: this run produced zero or more tool calls.
    tool_calls: Mapped[list[ToolCall]] = relationship(
        "ToolCall",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="ToolCall.created_at",
        lazy="select",
    )
