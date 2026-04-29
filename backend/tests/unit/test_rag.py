"""Unit tests for Stage 4 RAG components — loader, chunker, embedder, store.

All tests are offline (no Ollama, no Gemini API, no database).

WHAT IS TESTED
--------------
1. loader: load_file dispatches correctly for .md and .txt; raises on missing
   file and unsupported extension.
2. chunker: section-aware H2 splitting; fallback sliding window for plain text;
   source/index/section/destination/source_url set correctly; ChunkRecord frozen.
3. embedder: GeminiEmbedder._embed_batch raises ValueError on wrong dimension;
   get_embedder returns same instance on repeated calls.
4. store: VectorStore.upsert validates parallel list lengths; VectorStore.search
   and .count work against a fake session via a mock sessionmaker.
"""

from __future__ import annotations

import pathlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rag.chunker import ChunkRecord, chunk_document
from app.rag.loader import load_file


# ─── Loader ───────────────────────────────────────────────────────────────────


class TestLoadFile:
    def test_loads_markdown(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "doc.md"
        f.write_text("# Hello\nWorld.", encoding="utf-8")
        assert "Hello" in load_file(f)

    def test_loads_text(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "doc.txt"
        f.write_text("plain text", encoding="utf-8")
        assert load_file(f) == "plain text"

    def test_missing_file_raises(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_file(tmp_path / "nonexistent.md")

    def test_unsupported_extension_raises(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "file.xyz"
        f.write_text("data")
        with pytest.raises(ValueError, match="Unsupported file extension"):
            load_file(f)

    def test_loads_json(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "data.json"
        f.write_text('{"key": "value"}', encoding="utf-8")
        content = load_file(f)
        assert "key" in content

    def test_loads_csv(self, tmp_path: pathlib.Path) -> None:
        f = tmp_path / "data.csv"
        f.write_text("name,city\nAlice,Rome\n", encoding="utf-8")
        content = load_file(f)
        assert "Alice" in content


# ─── Chunker ──────────────────────────────────────────────────────────────────


_MD_DOC = """\
# Kyoto — Ancient Capital
*Style: Culture | Region: Asia*

Kyoto was Japan's imperial capital for over a thousand years.

## Character and Atmosphere

Unlike Tokyo's pace, Kyoto moves slowly. The city rewards wandering.

## Practical Information

**Cost per day:** USD 80–130. Capsule hotels from USD 30.

**Safety index:** 9.5/10. Extremely safe city.

## Travel Style Profile

beach_score: 2/10
culture_score: 10/10
cost_per_day_usd: 100
"""


class TestChunkDocument:
    def test_empty_text_returns_no_chunks(self) -> None:
        assert chunk_document("", source="test.md") == []

    def test_whitespace_only_returns_no_chunks(self) -> None:
        assert chunk_document("   \n\n  ", source="test.md") == []

    def test_short_text_is_single_chunk(self) -> None:
        chunks = chunk_document("Short text.", source="doc.md")
        assert len(chunks) == 1
        assert chunks[0].text == "Short text."

    # ── Section-aware (H2) tests ───────────────────────────────────────────

    def test_section_aware_splits_on_h2_headers(self) -> None:
        chunks = chunk_document(_MD_DOC, source="kyoto_wikivoyage.md")
        # Expect one chunk per section: preamble + 3 H2 sections = 4
        assert len(chunks) == 4

    def test_h1_preamble_is_first_chunk(self) -> None:
        chunks = chunk_document(_MD_DOC, source="kyoto_wikivoyage.md")
        # The preamble chunk has no section label (before first ##)
        assert chunks[0].section == ""
        assert "Kyoto" in chunks[0].text

    def test_section_labels_extracted_from_h2_headers(self) -> None:
        chunks = chunk_document(_MD_DOC, source="kyoto_wikivoyage.md")
        sections = [c.section for c in chunks]
        assert "Character and Atmosphere" in sections
        assert "Practical Information" in sections
        assert "Travel Style Profile" in sections

    def test_h2_header_line_included_in_chunk_text(self) -> None:
        chunks = chunk_document(_MD_DOC, source="kyoto_wikivoyage.md")
        practical = next(c for c in chunks if c.section == "Practical Information")
        assert "## Practical Information" in practical.text

    def test_destination_and_source_url_propagated(self) -> None:
        chunks = chunk_document(
            _MD_DOC,
            source="kyoto_wikivoyage.md",
            destination="Kyoto",
            source_url="https://en.wikivoyage.org/",
        )
        assert all(c.destination == "Kyoto" for c in chunks)
        assert all(c.source_url == "https://en.wikivoyage.org/" for c in chunks)

    def test_long_section_falls_back_to_sliding_window(self) -> None:
        # Build a section that is definitely > 1200 chars.
        long_section = "## Giant Section\n\n" + ("This is a sentence. " * 80)
        chunks = chunk_document(
            long_section,
            source="big.md",
            max_section_size=200,
            chunk_size=100,
            chunk_overlap=10,
        )
        # Should produce multiple chunks, all with the same section label.
        assert len(chunks) > 1
        assert all(c.section == "Giant Section" for c in chunks)

    def test_plain_text_falls_back_to_sliding_window(self) -> None:
        # Plain text without ## headers should produce chunks via sliding window.
        text = "This is a sentence. " * 40
        chunks = chunk_document(text, source="plain.txt", chunk_size=100, chunk_overlap=10)
        assert len(chunks) > 1
        assert all(c.section == "" for c in chunks)

    # ── Legacy sliding-window tests (still valid for the fallback path) ────

    def test_source_and_index_set_correctly(self) -> None:
        text = "Sentence one. " * 50
        chunks = chunk_document(text, source="kyoto.md", chunk_size=100, chunk_overlap=10)
        assert all(c.source == "kyoto.md" for c in chunks)
        assert [c.chunk_index for c in chunks] == list(range(len(chunks)))

    def test_no_chunk_exceeds_size_by_much(self) -> None:
        # Each chunk may slightly exceed chunk_size if the next sentence boundary
        # pushes it over; allow a generous margin of one sentence (~50 chars).
        text = "This is a sentence. " * 100
        chunks = chunk_document(text, source="test.md", chunk_size=200, chunk_overlap=20)
        for c in chunks:
            assert len(c.text) <= 300, f"Chunk too long: {len(c.text)}"

    def test_multiple_chunks_for_long_text(self) -> None:
        text = "A sentence that ends here. " * 50
        chunks = chunk_document(text, source="long.md", chunk_size=100, chunk_overlap=10)
        assert len(chunks) > 1

    def test_chunk_record_is_frozen(self) -> None:
        chunk = ChunkRecord(source="x.md", chunk_index=0, text="hi")
        with pytest.raises(Exception):
            chunk.text = "changed"  # type: ignore[misc]

    def test_chunk_record_default_fields(self) -> None:
        chunk = ChunkRecord(source="x.md", chunk_index=0, text="hi")
        assert chunk.section == ""
        assert chunk.destination == ""
        assert chunk.source_url == ""


# ─── Embedder ─────────────────────────────────────────────────────────────────


def _make_async_http_post(vec: list[float]) -> AsyncMock:
    """Build an async mock for httpx.AsyncClient.post returning one embedding."""
    # httpx.Response methods (raise_for_status, json) are synchronous.
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"embedding": {"values": vec}}
    return AsyncMock(return_value=response)


class TestGeminiEmbedder:
    def test_get_embedder_returns_same_instance(self) -> None:
        from app.rag.embedder import get_embedder

        e1 = get_embedder(api_key="fake", model="models/gemini-embedding-001", embed_dim=768)
        e2 = get_embedder(api_key="fake", model="models/gemini-embedding-001", embed_dim=768)
        assert e1 is e2

    @pytest.mark.asyncio
    async def test_embed_one_raises_on_wrong_dim(self) -> None:
        from app.rag.embedder import GeminiEmbedder

        embedder = GeminiEmbedder(api_key="fake", model="m", embed_dim=768)
        wrong_vec = [0.0] * 512  # wrong: expected 768
        with patch.object(embedder._http, "post", new=_make_async_http_post(wrong_vec)):
            with pytest.raises(ValueError, match="Expected embedding dim 768"):
                await embedder._embed_one("test", "RETRIEVAL_DOCUMENT")

    @pytest.mark.asyncio
    async def test_embed_one_accepts_correct_dim(self) -> None:
        from app.rag.embedder import GeminiEmbedder

        embedder = GeminiEmbedder(api_key="fake", model="m", embed_dim=4)
        correct_vec = [0.1, 0.2, 0.3, 0.4]
        with patch.object(embedder._http, "post", new=_make_async_http_post(correct_vec)):
            result = await embedder._embed_one("test", "RETRIEVAL_DOCUMENT")
        assert result == correct_vec


# ─── VectorStore ──────────────────────────────────────────────────────────────


class TestVectorStore:
    def test_upsert_mismatched_lengths_raises(self) -> None:
        from app.rag.store import VectorStore

        store = VectorStore(MagicMock())
        chunks = [ChunkRecord(source="x", chunk_index=0, text="hi")]
        vectors: list[list[float]] = []
        with pytest.raises(ValueError, match="same length"):
            import asyncio

            asyncio.run(store.upsert(chunks, vectors))

    def test_upsert_empty_returns_zero(self) -> None:
        from app.rag.store import VectorStore

        store = VectorStore(MagicMock())
        import asyncio

        result = asyncio.run(store.upsert([], []))
        assert result == 0

    @pytest.mark.asyncio
    async def test_count_returns_integer(self) -> None:
        from app.rag.store import VectorStore

        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=42)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_sessionmaker = MagicMock(return_value=mock_session)
        store = VectorStore(mock_sessionmaker)
        count = await store.count()
        assert count == 42

    @pytest.mark.asyncio
    async def test_search_returns_empty_on_empty_store(self) -> None:
        from app.rag.store import VectorStore

        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=0)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_sessionmaker = MagicMock(return_value=mock_session)
        store = VectorStore(mock_sessionmaker)
        results = await store.search([0.1] * 768)
        assert results == []
