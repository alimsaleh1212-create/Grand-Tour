"""Cached cheap + strong Gemini clients.

Implemented in Stage 5.

Design:
    * Two clients — `cheap` (gemini-2.5-flash) for routing and arg
      extraction, `strong` (gemini-2.5-pro) for final synthesis.
    * Both wrap the `google-generativeai` SDK and expose a uniform async
      `generate(...)` method that returns a typed result with token
      counts.
    * `max_output_tokens` is set on every call (per CLAUDE §19, point 4).
    * Tenacity wraps every call with retries + exponential backoff on
      429 / 5xx / timeouts. After the budget is exhausted the failure
      is logged with structure and re-raised as `ExternalAPIError`.
    * Clients are constructed by `@lru_cache(maxsize=1)` factories called
      from the lifespan handler; tests inject fakes via dependency override.

Public surface (planned):
    class GeminiClient:
        def __init__(self, model_name: str, max_output_tokens: int,
                     api_key: SecretStr): ...

        async def generate(
            self,
            *,
            system_prompt: str,
            user_prompt: str,
            response_schema: type[BaseModel] | None = None,
        ) -> GenerationResult: ...

    @dataclass
    class GenerationResult:
        text: str
        parsed: BaseModel | None     # populated when response_schema is given
        tokens_in: int
        tokens_out: int

    @lru_cache(maxsize=1)
    def get_cheap_client() -> GeminiClient: ...

    @lru_cache(maxsize=1)
    def get_strong_client() -> GeminiClient: ...
"""
