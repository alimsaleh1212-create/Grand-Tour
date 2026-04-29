"""Sentence-aware, section-aware text chunker.

Strategy — two-level:
    1. PRIMARY (markdown documents): split on H2 headers (## ...).
       Each H2 section becomes one chunk — sections are semantically
       independent (cost, safety, activities, etc.), so one chunk per
       section gives retrieval a clean, focused unit.

    2. FALLBACK (oversized sections or plain text): if a section exceeds
       max_section_size characters, apply the sentence-boundary sliding
       window to that section alone.  This prevents giant chunks that
       exceed the embedding context window.

Why H2 splitting is better than fixed-size windows for our documents:
    - Each H2 section answers a different query class ("what does it cost?",
      "what are the top sights?", "how safe is it?").
    - The Travel Style Profile section contains structured scores
      (beach_score, cost_per_day_usd).  A mid-section cut loses half the
      scores, degrading classifier retrieval.
    - Section sizes in our knowledge files range 80-500 words — all fit
      within one embedding without needing a sliding window.

ChunkRecord fields:
    source      : filename, e.g. "kyoto_wikivoyage.md"
    chunk_index : 0-based position within the source document
    text        : full chunk text (includes H2 header line for context)
    section     : H2 header label, e.g. "Practical Information"; "" for preamble
    destination : human-readable destination name, e.g. "Kyoto"
    source_url  : origin website base URL, e.g. "https://en.wikivoyage.org/"

Public surface:
    @dataclass(frozen=True)
    class ChunkRecord: source, chunk_index, text, section, destination, source_url

    chunk_document(
        text, *, source, destination, source_url,
        chunk_size, chunk_overlap, max_section_size
    ) -> list[ChunkRecord]
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 50
DEFAULT_MAX_SECTION = 1200

_SENTENCE_ENDINGS = (". ", "! ", "? ", ".\n", "!\n", "?\n")

# Matches the start of an H2 block ("## " at the beginning of a line).
_H2_SPLIT = re.compile(r"(?m)^(?=## )")
# Captures the H2 header label from the first line of an H2 block.
_H2_HEADER = re.compile(r"^## (.+)$", re.MULTILINE)


@dataclass(frozen=True)
class ChunkRecord:
    """One chunk of a source document, ready for embedding.

    All fields default to empty string so existing call-sites that only
    pass source/chunk_index/text keep working.
    """

    source: str
    chunk_index: int
    text: str
    section: str = field(default="")
    destination: str = field(default="")
    source_url: str = field(default="")


def chunk_document(
    text: str,
    *,
    source: str,
    destination: str = "",
    source_url: str = "",
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    max_section_size: int = DEFAULT_MAX_SECTION,
) -> list[ChunkRecord]:
    """Split `text` into section-aware, overlapping chunks.

    For markdown documents with H2 headers the primary strategy is one
    chunk per section.  Plain-text documents (or overlong sections) fall
    back to the sentence-boundary sliding window.

    Args:
        text: Full document text.
        source: Document identifier, e.g. "kyoto_wikivoyage.md".
        destination: Human-readable destination name, e.g. "Kyoto".
        source_url: Origin website base URL, e.g. "https://en.wikivoyage.org/".
        chunk_size: Character target used only by the sliding-window fallback.
        chunk_overlap: Overlap characters used only by the sliding-window fallback.
        max_section_size: Sections larger than this fall back to sliding window.

    Returns:
        List of ChunkRecord, indexed from 0.
    """
    text = text.strip()
    if not text:
        return []

    # Try the primary H2-based split.
    parts = _H2_SPLIT.split(text)

    # If the document has no H2 headers, parts == [text] — fall through to
    # the sliding window for the whole document.
    has_sections = any(_H2_HEADER.match(p) for p in parts)

    chunks: list[ChunkRecord] = []
    idx = 0

    if has_sections:
        for part in parts:
            part = part.strip()
            if not part:
                continue
            m = _H2_HEADER.match(part)
            section = m.group(1).strip() if m else ""

            if len(part) <= max_section_size:
                chunks.append(
                    ChunkRecord(
                        source=source,
                        chunk_index=idx,
                        text=part,
                        section=section,
                        destination=destination,
                        source_url=source_url,
                    )
                )
                idx += 1
            else:
                # Oversized section — sliding window within this section only.
                for sub_text in _sliding_window(part, chunk_size, chunk_overlap):
                    chunks.append(
                        ChunkRecord(
                            source=source,
                            chunk_index=idx,
                            text=sub_text,
                            section=section,
                            destination=destination,
                            source_url=source_url,
                        )
                    )
                    idx += 1
    else:
        # Plain text or single-section document — sliding window over full text.
        for sub_text in _sliding_window(text, chunk_size, chunk_overlap):
            chunks.append(
                ChunkRecord(
                    source=source,
                    chunk_index=idx,
                    text=sub_text,
                    section="",
                    destination=destination,
                    source_url=source_url,
                )
            )
            idx += 1

    return chunks


# ── Sliding-window fallback ────────────────────────────────────────────────────


def _sliding_window(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """Return overlapping sentence-aware chunks of `text`."""
    text = text.strip()
    if not text:
        return []

    results: list[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            chunk_text = text[start:].strip()
        else:
            boundary = _last_sentence_boundary(text, start, end)
            chunk_text = text[start:boundary].strip()
            end = boundary

        if chunk_text:
            results.append(chunk_text)

        if end >= len(text):
            break

        advance = max(1, chunk_size - chunk_overlap)
        start = start + advance

    return results


def _last_sentence_boundary(text: str, start: int, end: int) -> int:
    """Return the position of the last sentence ending in text[start:end].

    Falls back to `end` if no sentence boundary exists.
    """
    window = text[start:end]
    best = -1
    for ending in _SENTENCE_ENDINGS:
        pos = window.rfind(ending)
        if pos > best:
            best = pos
    if best == -1:
        return end
    for ending in _SENTENCE_ENDINGS:
        if window[best : best + len(ending)] == ending:
            return start + best + len(ending)
    return start + best + 2
