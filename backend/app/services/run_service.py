"""AgentRun lifecycle service.

Implemented in Stage 6.

Public surface (planned):
    async def create_run(
        session: AsyncSession,
        *,
        user_id: int,
        question: str,
    ) -> AgentRun: ...

    async def append_tool_call(
        session: AsyncSession,
        *,
        run_id: int,
        tool_name: str,
        args: dict,
        result: dict | None,
        tokens: int,
        latency_ms: int,
        error: str | None,
    ) -> ToolCall: ...

    async def finalise_run(
        session: AsyncSession,
        *,
        run_id: int,
        final_answer: str,
        total_tokens_cheap: int,
        total_tokens_strong: int,
        cost_usd: float,
    ) -> AgentRun: ...

    async def list_runs_for_user(
        session: AsyncSession,
        *,
        user_id: int,
        limit: int = 50,
    ) -> list[AgentRun]: ...

    async def get_run_for_user(
        session: AsyncSession,
        *,
        user_id: int,
        run_id: int,
    ) -> AgentRun | None: ...
"""
