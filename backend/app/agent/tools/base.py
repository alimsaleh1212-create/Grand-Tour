"""BaseTool — abstract contract for every agent tool.

Implemented in Stage 5.

Why an ABC: every tool MUST validate its inputs before running, MUST
convert exceptions to structured results (so the LangGraph node can hand
them back to the LLM as text), and MUST advertise a Pydantic input/output
schema. Encoding that as an ABC means a fourth tool added later cannot
forget any of these invariants.

Public surface (planned):
    class ToolResult(BaseModel, Generic[OutputT]):
        ok: bool
        output: OutputT | None = None
        error: str | None = None
        latency_ms: int

    class BaseTool(ABC, Generic[InputT, OutputT]):
        name: ClassVar[str]                  # used by the allowlist
        input_schema: ClassVar[type[BaseModel]]
        output_schema: ClassVar[type[BaseModel]]

        @abstractmethod
        async def run(self, args: InputT) -> OutputT:
            # The actual work. May raise — safe_run wraps.
            ...

        async def safe_run(self, raw_args: dict) -> ToolResult[OutputT]:
            # 1. Validate raw_args against input_schema → structured
            #    ToolValidationError on failure.
            # 2. Time the run.
            # 3. Catch ExternalAPIError, ToolUnavailableError, etc., and
            #    return them as ToolResult(ok=False, error=...).
            # 4. Never re-raise into the agent loop.
            ...

The agent's LangGraph node calls ONLY `safe_run`.
"""
