"""Cached cheap + strong Gemini text-generation clients.

TWO TIERS
---------
    cheap  (gemini-2.5-flash) — extraction, routing, feature parsing.
                                Fires many times per request.
    strong (gemini-2.5-pro)   — final synthesis. Fires ONCE per request.

WHY google-genai SDK (not REST)
-------------------------------
Unlike the embedding endpoint (which has model-availability quirks that
forced us to call REST directly), the standard generation models
(gemini-2.5-flash, gemini-2.5-pro) are fully supported by the google-genai
SDK and do not require manual endpoint construction.

RETRY POLICY
------------
Tenacity retries on 429 (rate-limit) and 5xx / network errors.  Never retries
on 4xx (bad key, bad request) — those fail the same way every time.

PUBLIC SURFACE
--------------
    @dataclass
    class GenerationResult:
        text: str
        parsed: BaseModel | None
        tokens_in: int
        tokens_out: int

    class GeminiClient:
        async def generate(*, system_prompt, user_prompt,
                           response_schema=None) -> GenerationResult

    def get_cheap_client(api_key, max_output_tokens) -> GeminiClient
    def get_strong_client(api_key, max_output_tokens) -> GeminiClient
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from google import genai
from google.genai import types as gtypes
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = logging.getLogger(__name__)

# ── Exceptions we retry on ────────────────────────────────────────────────────
# google-genai raises google.genai.errors.* on API failures.  We catch the
# broad base exception and also network-level errors.
try:
    from google.genai import errors as _genai_errors

    _RETRYABLE = (
        _genai_errors.ServerError,
        _genai_errors.TooManyRequests,
        ConnectionError,
        TimeoutError,
    )
except Exception:
    _RETRYABLE = (ConnectionError, TimeoutError)  # type: ignore[assignment]


@dataclass
class GenerationResult:
    """Structured result from a single Gemini call.

    Attributes:
        text: Raw text response from the model.
        parsed: Populated when response_schema is given and the model
            returned valid JSON that Pydantic accepted.
        tokens_in: Number of prompt tokens billed.
        tokens_out: Number of completion tokens billed.
    """

    text: str
    parsed: BaseModel | None
    tokens_in: int
    tokens_out: int


class GeminiClient:
    """Thin async wrapper around the google-genai SDK for one model tier.

    Args:
        model_name: Gemini model identifier (e.g. "gemini-2.5-flash").
        max_output_tokens: Hard cap on completion length — prevents runaway
            costs and limits exfiltration payloads.
        api_key: Google AI Studio API key.
    """

    def __init__(
        self, *, model_name: str, max_output_tokens: int, api_key: str
    ) -> None:
        self._model = model_name
        self._max_tokens = max_output_tokens
        self._client = genai.Client(api_key=api_key)

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel] | None = None,
        temperature: float = 0.0,
    ) -> GenerationResult:
        """Generate a completion from the model.

        Args:
            system_prompt: Static role/format/invariant instructions.
            user_prompt: The varying, per-request query (already sanitised
                and wrapped in <user_input> tags by the caller).
            response_schema: Optional Pydantic model.  When provided, the
                model is instructed to return valid JSON matching the schema,
                and the result is parsed into `GenerationResult.parsed`.
            temperature: Sampling temperature.  Default 0.0 for determinism.

        Returns:
            GenerationResult with text, optional parsed model, and token counts.
        """
        config_kwargs: dict[str, Any] = {
            "max_output_tokens": self._max_tokens,
            "temperature": temperature,
            "system_instruction": system_prompt,
        }
        if response_schema is not None:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = response_schema

        config = gtypes.GenerateContentConfig(**config_kwargs)

        response = await self._retry_generate(user_prompt, config)

        text: str = response.text or ""
        usage = response.usage_metadata
        tokens_in = getattr(usage, "prompt_token_count", 0) or 0
        tokens_out = getattr(usage, "candidates_token_count", 0) or 0

        parsed: BaseModel | None = None
        if response_schema is not None and text:
            try:
                import json

                parsed = response_schema.model_validate(json.loads(text))
            except Exception as exc:
                log.warning(
                    "llm.parse_failed",
                    extra={
                        "model": self._model,
                        "schema": response_schema.__name__,
                        "error": str(exc),
                    },
                )

        log.debug(
            "llm.generate",
            extra={
                "model": self._model,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "schema": response_schema.__name__ if response_schema else None,
            },
        )
        return GenerationResult(
            text=text, parsed=parsed, tokens_in=tokens_in, tokens_out=tokens_out
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(_RETRYABLE),
        reraise=True,
    )
    async def _retry_generate(
        self,
        user_prompt: str,
        config: gtypes.GenerateContentConfig,
    ) -> Any:
        return await self._client.aio.models.generate_content(
            model=self._model,
            contents=user_prompt,
            config=config,
        )


@lru_cache(maxsize=1)
def get_cheap_client(api_key: str, max_output_tokens: int) -> GeminiClient:
    """Return the process-wide cheap (Flash) client singleton."""
    settings_model = _read_model_name("cheap")
    return GeminiClient(
        model_name=settings_model,
        max_output_tokens=max_output_tokens,
        api_key=api_key,
    )


@lru_cache(maxsize=1)
def get_strong_client(api_key: str, max_output_tokens: int) -> GeminiClient:
    """Return the process-wide strong (Pro) client singleton."""
    settings_model = _read_model_name("strong")
    return GeminiClient(
        model_name=settings_model,
        max_output_tokens=max_output_tokens,
        api_key=api_key,
    )


def _read_model_name(tier: str) -> str:
    """Read cheap/strong model name from Settings without circular import."""
    from app.core.settings import get_settings

    s = get_settings()
    return s.gemini_cheap_model if tier == "cheap" else s.gemini_strong_model
