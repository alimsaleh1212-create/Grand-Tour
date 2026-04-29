"""Prompt-injection guardrails (CLAUDE §19).

Implemented in Stage 5 — but conservatively, since this is a security file.

Functions (planned):
    def _sanitize_query(query: str, *, max_len: int = 2000) -> str:
        # 1. Normalize whitespace.
        # 2. Strip control characters.
        # 3. Truncate to max_len.
        # 4. Remove or escape lines beginning with role markers
        #    (system:, assistant:, ###, ---), which are common
        #    prompt-injection vectors.
        # 5. Log a WARNING if any suspicious pattern fires (do NOT
        #    reject — let the request through but record it).

    def _sanitize_feature_string(value: str, *, max_len: int = 200) -> str:
        # For LLM string outputs that flow back into a prompt or a tool
        # arg (e.g. extracted destination name → next tool). Same hygiene
        # as _sanitize_query but tighter cap.

    def log_suspicious_patterns(text: str) -> None:
        # Pure logging hook — runs the regex panel
        # (ignore previous, you are now, system prompt, \\n\\nHuman:, etc.)

Constants (planned):
    SUSPICIOUS_PATTERNS: tuple[re.Pattern, ...]
"""
