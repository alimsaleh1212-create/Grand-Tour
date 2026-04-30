"""BaseTool — abstract contract every agent tool must implement.

WHY AN ABC
----------
Three invariants must hold for every tool:
  1. Input validated against a Pydantic schema before run() is called.
  2. Exceptions converted to ToolResult(ok=False) — never propagate into the
     LangGraph loop.
  3. Latency measured and returned alongside the result.

Encoding this as an ABC means a fourth tool added later cannot skip any of
these invariants without a mypy --strict failure.

PUBLIC SURFACE
--------------
    @dataclass
    class ToolResult(Generic[OutputT]):
        ok: bool
        output: OutputT | None
        error: str | None
        latency_ms: int

    class BaseTool(ABC, Generic[InputT, OutputT]):
        name: ClassVar[str]
        input_schema: ClassVar[type[BaseModel]]
        output_schema: ClassVar[type[BaseModel]]

        @abstractmethod
        async def run(self, args: InputT) -> OutputT: ...

        async def safe_run(self, raw_args: dict) -> ToolResult[OutputT]: ...
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.exceptions import ExternalAPIError, ToolError, ToolUnavailableError

log = logging.getLogger(__name__)

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


@dataclass
class ToolResult(Generic[OutputT]):
    """Structured result from BaseTool.safe_run().

    Attributes:
        ok: True on success, False on any error.
        output: The tool's return value.  None when ok is False.
        error: Human-readable error description.  None when ok is True.
        latency_ms: Wall-clock time in milliseconds from safe_run entry to exit.
    """

    ok: bool
    output: OutputT | None
    error: str | None
    latency_ms: int


class BaseTool(ABC, Generic[InputT, OutputT]):
    """Abstract base for all agent tools.

    Subclasses must set three class variables and implement run().
    safe_run() is the ONLY entry point the LangGraph node calls.
    """

    name: ClassVar[str]
    input_schema: ClassVar[type[BaseModel]]
    output_schema: ClassVar[type[BaseModel]]

    @abstractmethod
    async def run(self, args: InputT) -> OutputT:
        """Execute the tool logic.

        Args:
            args: Validated input model.

        Returns:
            Populated output model.

        Raises:
            ExternalAPIError: On network / upstream failure after retries.
            ToolUnavailableError: On configuration failure (e.g. missing key).
        """
        ...

    async def safe_run(self, raw_args: dict[str, object]) -> ToolResult[OutputT]:
        """Validate → run → catch exceptions.

        This method never raises.  Exceptions become ToolResult(ok=False).

        Args:
            raw_args: Unvalidated dict of arguments from the LLM or caller.

        Returns:
            ToolResult with ok=True and output on success,
            or ok=False and error on any failure.
        """
        start = time.monotonic()

        try:
            args: InputT = self.input_schema.model_validate(raw_args)
        except ValidationError as exc:
            latency = int((time.monotonic() - start) * 1000)
            log.warning(
                "tool.validation_error",
                extra={"tool": self.name, "error": str(exc)},
            )
            return ToolResult(
                ok=False,
                output=None,
                error=f"Invalid arguments: {exc}",
                latency_ms=latency,
            )

        try:
            output = await self.run(args)  # type: ignore[arg-type]
            latency = int((time.monotonic() - start) * 1000)
            log.info(
                "tool.success",
                extra={"tool": self.name, "latency_ms": latency},
            )
            return ToolResult(ok=True, output=output, error=None, latency_ms=latency)

        except (ToolError, ExternalAPIError, ToolUnavailableError) as exc:
            latency = int((time.monotonic() - start) * 1000)
            log.warning(
                "tool.error",
                extra={"tool": self.name, "error": str(exc), "latency_ms": latency},
            )
            return ToolResult(
                ok=False, output=None, error=str(exc), latency_ms=latency
            )

        except Exception as exc:
            latency = int((time.monotonic() - start) * 1000)
            log.error(
                "tool.unexpected_error",
                extra={"tool": self.name, "latency_ms": latency},
                exc_info=True,
            )
            return ToolResult(
                ok=False,
                output=None,
                error=f"Unexpected error in {self.name}: {type(exc).__name__}",
                latency_ms=latency,
            )
