"""Prompt-injection guardrails (CLAUDE.md §15).

Public surface:
    SUSPICIOUS_PATTERNS: tuple[re.Pattern, ...]

    def sanitize_query(query: str, *, max_len: int = 2000) -> str
    def sanitize_feature_string(value: str, *, max_len: int = 200) -> str
    def log_suspicious_patterns(text: str) -> None
"""

from __future__ import annotations

import logging
import re
import unicodedata

log = logging.getLogger(__name__)

# Patterns that commonly appear in prompt-injection attempts.
# We log but do NOT reject — let the request through so the user isn't
# silently blocked on a false positive.
SUSPICIOUS_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore\s+(?:all\s+)?previous", re.I),
    re.compile(r"you\s+are\s+now", re.I),
    re.compile(r"system\s*:?\s*prompt", re.I),
    re.compile(r"\n\nHuman\s*:", re.I),
    re.compile(r"###\s*(?:system|assistant|instruction)", re.I),
    re.compile(r"</?(?:system|instruction|context)>", re.I),
    re.compile(r"disregard\s+(?:all\s+)?(?:previous|prior|above)", re.I),
)

# Whole lines whose first token is a role marker are stripped — these are a
# common vector for injecting fake system turns into the prompt.
_ROLE_LINE = re.compile(
    r"^(?:system|assistant|###\s*system|---)\s*:.*$", re.I | re.MULTILINE
)

# Characters below U+0020 that are not ordinary whitespace (\t \n \r).
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_query(query: str, *, max_len: int = 2000) -> str:
    """Sanitize a raw user query before it enters any prompt template.

    Steps:
        1. Normalize unicode to NFC (collapse composed/decomposed forms).
        2. Strip ASCII control characters (keep \\t, \\n, \\r).
        3. Remove lines that begin with role-marker prefixes.
        4. Normalize runs of whitespace (>2 consecutive blank lines → 2).
        5. Truncate to max_len.
        6. Log a WARNING for each suspicious pattern found (no rejection).

    Args:
        query: Raw user-supplied string.
        max_len: Hard character cap. Default 2 000.

    Returns:
        Cleaned string, never longer than max_len chars.
    """
    text = unicodedata.normalize("NFC", query)
    text = _CONTROL_CHARS.sub("", text)
    text = _ROLE_LINE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()[:max_len]
    log_suspicious_patterns(text)
    return text


def sanitize_feature_string(value: str, *, max_len: int = 200) -> str:
    """Sanitize an LLM-produced string before re-use in another prompt.

    Applies the same hygiene as sanitize_query but with a tighter cap (200
    chars) since these strings are LLM outputs flowing back into prompts or
    tool arguments — they should be short and clean.

    Args:
        value: String produced by the cheap LLM (e.g. extracted destination
            name, region label).
        max_len: Hard character cap. Default 200.

    Returns:
        Cleaned string, never longer than max_len chars.
    """
    return sanitize_query(value, max_len=max_len)


def log_suspicious_patterns(text: str) -> None:
    """Log a WARNING for every suspicious pattern found in *text*.

    Pure side-effect — never modifies the string, never blocks the request.
    Called from sanitize_query and may be called independently on any
    string that flows into a prompt (e.g. LLM tool output).

    Args:
        text: Arbitrary string to scan.
    """
    for pattern in SUSPICIOUS_PATTERNS:
        if pattern.search(text):
            log.warning(
                "security.suspicious_pattern",
                extra={"pattern": pattern.pattern, "snippet": text[:120]},
            )
