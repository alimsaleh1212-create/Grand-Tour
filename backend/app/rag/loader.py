"""Source-document loader — file path to plain text.

Implemented in Stage 4.

Design: dispatch on extension; keep all format-specific code here so the
chunker only ever sees plain text.

Public surface (planned):
    def load_file(path: Path) -> str: ...
        # Dispatches to private helpers based on suffix. Raises
        # `RAGError` on unsupported types or unreadable files.

    def _load_markdown(path: Path) -> str: ...
    def _load_text(path: Path) -> str: ...
    def _load_pdf(path: Path) -> str: ...
    def _load_csv(path: Path) -> str: ...
    def _load_json(path: Path) -> str: ...

Graceful degradation: if optional readers (e.g. pypdf) are absent the
loader returns a clear placeholder string rather than crashing the
ingest run, per the mentor guidelines pattern.
"""
