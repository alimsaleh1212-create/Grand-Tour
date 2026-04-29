"""Sentence-aware text chunker.

Implemented in Stage 4.

Design (per mentor guidelines):
    * Sentence-aware boundaries (find the last ". " before the hard cut)
      so we never embed half a sentence.
    * Overlapping windows preserve context across boundaries.
    * Pure function — same text + same params → same chunks; trivial to
      unit-test.

Defaults come from Settings (`default_chunk_size=500`, `default_chunk_overlap=50`).
Justifications go in the README's "Chunking & retrieval rationale" section.

Public surface (planned):
    @dataclass(frozen=True)
    class ChunkRecord:
        source: str
        chunk_index: int
        text: str

    def chunk_document(
        text: str,
        *,
        source: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> list[ChunkRecord]: ...
"""
