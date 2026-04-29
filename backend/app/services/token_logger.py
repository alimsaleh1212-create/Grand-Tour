"""Token accounting helper for two-model agent runs.

Implemented in Stage 5.

Why a dedicated helper:
    The agent makes many cheap-model calls (routing, arg extraction) and
    one or two strong-model calls (synthesis). The brief asks for token
    usage AND cost per query reported in the README. Centralising the
    accumulation here keeps the LangGraph nodes thin.

Public surface (planned):
    @dataclass
    class TokenUsage:
        cheap_in: int = 0
        cheap_out: int = 0
        strong_in: int = 0
        strong_out: int = 0

        def add(self, *, model_tier: Literal["cheap", "strong"],
                in_tokens: int, out_tokens: int) -> None: ...

        def total_tokens_cheap(self) -> int: ...
        def total_tokens_strong(self) -> int: ...
        def cost_usd(self, prices: TokenPrices) -> float: ...

    class TokenPrices(BaseModel):
        cheap_in_per_1k: float
        cheap_out_per_1k: float
        strong_in_per_1k: float
        strong_out_per_1k: float
"""
