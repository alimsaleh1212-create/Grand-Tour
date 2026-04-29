"""Source-document loader — file path to plain text.

Public surface:
    load_file(path: Path) -> str
        Dispatches to private helpers based on file suffix.
        Raises FileNotFoundError on missing path.
        Raises ValueError on unsupported extension.

Supported formats: .md, .txt, .pdf (requires pypdf), .csv, .json.
"""

from __future__ import annotations

import csv
import json
import pathlib


def load_file(path: pathlib.Path) -> str:
    """Load a document file and return its contents as plain text.

    Args:
        path: Absolute or relative path to the source document.

    Returns:
        Plain UTF-8 text of the document.

    Raises:
        FileNotFoundError: If the path does not exist.
        ValueError: If the file extension is not supported.
    """
    path = pathlib.Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {path}")

    suffix = path.suffix.lower()
    dispatch = {
        ".md": _load_markdown,
        ".txt": _load_text,
        ".pdf": _load_pdf,
        ".csv": _load_csv,
        ".json": _load_json,
    }
    handler = dispatch.get(suffix)
    if handler is None:
        raise ValueError(
            f"Unsupported file extension {suffix!r}. "
            f"Supported: {sorted(dispatch)}"
        )
    return handler(path)


def _load_markdown(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_pdf(path: pathlib.Path) -> str:
    try:
        import pypdf  # type: ignore[import]
    except ImportError:
        return f"[PDF loader unavailable — install pypdf to process {path.name}]"
    reader = pypdf.PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _load_csv(path: pathlib.Path) -> str:
    lines: list[str] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lines.append(", ".join(f"{k}: {v}" for k, v in row.items()))
    return "\n".join(lines)


def _load_json(path: pathlib.Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    return json.dumps(data, ensure_ascii=False, indent=2)
