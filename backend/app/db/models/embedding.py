"""Embedding ORM model — RAG chunk stored in pgvector.

HOW THIS MODEL FITS INTO THE DATA FLOW
----------------------------------------
    Ingestion (Stage 4) — rag/scripts/ingest.py
        → load knowledge text → chunk (section-aware) → embed via Gemini
        → store.upsert(source, chunk_index, text, section, destination,
                        source_url, vector)
        → Embedding row upserted (ON CONFLICT DO UPDATE)

    Retrieval (Stage 5) — tools/retrieve_destinations.py
        → embed the user query → vector similarity search
        → SELECT ... ORDER BY vector <=> ? LIMIT k
        → returns SearchHit(text, section, destination, source_url, distance)
          to the agent as structured, citable context

WHY SEPARATE destination AND source_url COLUMNS
------------------------------------------------
Storing these as top-level columns (not buried in the text payload) lets the
agent perform deterministic citations: the retrieve_destinations tool returns
destination and source_url as standalone fields in its output, so the LLM
never has to parse citation info from prose.  The destination field is also
passed directly to the classify_style tool so the ML classifier receives a
clean, machine-derived input — not a text extraction from prose.

WHY section COLUMN
-------------------
Each H2 section of a travel guide answers a different query class (cost,
safety, activities, …).  Storing the section label lets the agent cite not
just the document but the specific section — improving answer traceability.

WHY COMPOSITE UNIQUE KEY ON (source, chunk_index)
---------------------------------------------------
Idempotent upserts: re-ingesting the same document replaces the existing
embedding vector rather than creating a duplicate.

WHY Vector(768) AND NOT A HARD-CODED 768
-----------------------------------------
Settings.embed_dim drives the dimension.  768 matches text-embedding-004
(Gemini).  Switching models requires an Alembic migration — documented in
the root README.

WHY THIS IS IN Stage 2 MODELS BUT IMPLEMENTED IN Stage 4
----------------------------------------------------------
The model is declared now so the first Alembic migration creates the full
schema in one transaction (including CREATE EXTENSION vector).  The
application code that uses this model (rag/store.py, tools/retrieve) is
wired in Stage 4.
"""

from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Embedding(TimestampMixin, Base):
    """One chunk of knowledge text + its embedding vector.

    Columns
    -------
    id          : surrogate PK
    source      : filename, e.g. "kyoto_wikivoyage.md"
    chunk_index : 0-based position within source
    text        : raw chunk text returned to the agent as context
    section     : H2 header label, e.g. "Practical Information"; empty for preamble
    destination : human-readable destination name, e.g. "Kyoto"
    source_url  : origin website base URL, e.g. "https://en.wikivoyage.org/"
    vector      : pgvector(768) embedding from Gemini text-embedding-004
    """

    __tablename__ = "embeddings"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "chunk_index",
            name="uq_embeddings_source_chunk",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    source: Mapped[str] = mapped_column(String(512), nullable=False, index=True)

    chunk_index: Mapped[int] = mapped_column(nullable=False)

    text: Mapped[str] = mapped_column(Text, nullable=False)

    # Section label from the H2 header — empty string for preamble chunks.
    section: Mapped[str] = mapped_column(String(256), nullable=False, server_default="")

    # Destination name and source URL stored as dedicated columns so the
    # retrieve tool can return them as structured citation fields without
    # any text parsing.
    destination: Mapped[str] = mapped_column(
        String(256), nullable=False, server_default=""
    )
    source_url: Mapped[str] = mapped_column(
        String(512), nullable=False, server_default=""
    )

    # Vector dimension matches Settings.embed_dim (768 for text-embedding-004).
    # Changing the embedding model requires an Alembic migration.
    vector: Mapped[list[float]] = mapped_column(
        Vector(768),
        nullable=False,
    )
