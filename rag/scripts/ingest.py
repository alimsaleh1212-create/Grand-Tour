"""One-shot ingestion CLI: knowledge files → pgvector store.

Usage (run from the project root, not ml/ or rag/):
    uv run python -m rag.scripts.ingest                        # all files
    uv run python -m rag.scripts.ingest --paths kyoto.md ...  # selected

Pipeline:
    1. Iterate rag/data/knowledge/*.{md,txt,pdf,csv,json}.
    2. For each file: loader.load_file() → plain text.
    3. Parse destination name and source URL from the filename.
       Convention: <destination>_<source>.md
       e.g. kyoto_wikivoyage.md → destination="Kyoto", source_url="https://en.wikivoyage.org/"
    4. chunker.chunk_document() — section-aware H2 splitting with Settings defaults.
    5. embedder.embed_texts() — async, batched via Gemini API.
    6. store.upsert(chunks, vectors) — idempotent on (source, chunk_index).
    7. Print summary: files processed, chunks upserted, elapsed seconds.

Re-running is safe — existing rows are updated, not duplicated.

Destination + Source URL convention
-------------------------------------
Filenames follow the pattern: {destination}_{source}.md
Multi-word destinations use underscores between words, e.g. chiang_mai.
The last underscore-separated segment identifies the source provider.

Source provider → base URL mapping:
    wikivoyage  → https://en.wikivoyage.org/
    lonelyplanet → https://www.lonelyplanet.com/
    nomadlist   → https://nomadlist.com/

The destination name is title-cased (underscores replaced with spaces).
Example: chiang_mai_wikivoyage.md → "Chiang Mai", "https://en.wikivoyage.org/"

Requires:
    GOOGLE_API_KEY in environment (or .env in the working directory).
    Running Postgres with pgvector extension enabled (via docker compose).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import pathlib
import time

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

KNOWLEDGE_DIR = pathlib.Path(__file__).parent.parent / "data" / "knowledge"

# Maps the last segment of a filename stem to a base URL for citations.
_SOURCE_URL_MAP: dict[str, str] = {
    "wikivoyage": "https://en.wikivoyage.org/",
    "lonelyplanet": "https://www.lonelyplanet.com/",
    "nomadlist": "https://nomadlist.com/",
}


def _parse_destination_and_source(path: pathlib.Path) -> tuple[str, str]:
    """Extract destination name and source URL from a knowledge filename.

    Splits the stem (without extension) on the last underscore to separate
    the destination part from the source provider key.

    Args:
        path: Path to a knowledge file, e.g. Path("chiang_mai_wikivoyage.md").

    Returns:
        (destination, source_url) — e.g. ("Chiang Mai", "https://en.wikivoyage.org/")
        source_url is "" if the provider key is unrecognised.
    """
    stem = path.stem  # e.g. "chiang_mai_wikivoyage"
    # Split from the right on "_" once to separate provider from destination.
    last_underscore = stem.rfind("_")
    if last_underscore == -1:
        # No underscore — treat the whole stem as the destination.
        return stem.replace("_", " ").title(), ""
    dest_part = stem[:last_underscore]  # e.g. "chiang_mai"
    source_key = stem[last_underscore + 1 :]  # e.g. "wikivoyage"
    destination = dest_part.replace("_", " ").title()  # e.g. "Chiang Mai"
    source_url = _SOURCE_URL_MAP.get(source_key, "")
    return destination, source_url


async def _ingest(paths: list[pathlib.Path]) -> None:
    # Local imports so we can run from project root without installing the backend package.
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent / "backend"))

    from app.core.settings import get_settings
    from app.rag.chunker import chunk_document
    from app.rag.embedder import get_embedder
    from app.rag.loader import load_file
    from app.rag.store import VectorStore

    settings = get_settings()

    engine = create_async_engine(settings.async_database_url, echo=False)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    store = VectorStore(SessionLocal)
    embedder = get_embedder(
        api_key=settings.google_api_key.get_secret_value(),
        model=settings.gemini_embed_model,
        embed_dim=settings.embed_dim,
    )

    total_chunks = 0
    start = time.perf_counter()

    for path in paths:
        print(f"  {path.name} ...", end=" ", flush=True)
        destination, source_url = _parse_destination_and_source(path)
        text = load_file(path)
        chunks = chunk_document(
            text,
            source=path.name,
            destination=destination,
            source_url=source_url,
            chunk_size=settings.default_chunk_size,
            chunk_overlap=settings.default_chunk_overlap,
        )
        if not chunks:
            print("(empty, skipped)")
            continue

        # Print section breakdown for transparency.
        sections = [c.section or "(preamble)" for c in chunks]
        texts = [c.text for c in chunks]
        vectors = await embedder.embed_texts(texts, task_type="RETRIEVAL_DOCUMENT")
        upserted = await store.upsert(chunks, vectors)
        total_chunks += upserted
        section_summary = ", ".join(f'"{s}"' for s in sections)
        print(f"{upserted} chunks [{section_summary}]")

    elapsed = time.perf_counter() - start
    count = await store.count()
    await engine.dispose()

    print(f"\nDone: {len(paths)} files, {total_chunks} chunks upserted in {elapsed:.1f}s")
    print(f"Total rows in store: {count}")


def _resolve_paths(args_paths: list[str] | None) -> list[pathlib.Path]:
    if args_paths:
        return [pathlib.Path(p) for p in args_paths]
    supported = {".md", ".txt", ".pdf", ".csv", ".json"}
    return sorted(p for p in KNOWLEDGE_DIR.iterdir() if p.suffix in supported)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest knowledge documents into pgvector.")
    parser.add_argument(
        "--paths",
        nargs="+",
        metavar="PATH",
        help="Specific files to ingest (default: all files in rag/data/knowledge/)",
    )
    args = parser.parse_args()

    paths = _resolve_paths(args.paths)
    if not paths:
        print("No files found in", KNOWLEDGE_DIR)
        return

    print(f"Ingesting {len(paths)} file(s):")
    asyncio.run(_ingest(paths))


if __name__ == "__main__":
    main()
