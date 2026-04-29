"""Embedding ORM model — RAG chunk stored in pgvector.

HOW THIS MODEL FITS INTO THE DATA FLOW
----------------------------------------
    Ingestion (Stage 4) — rag/scripts/ingest.py
        → load knowledge text → chunk → embed via Ollama
        → store.upsert(source, chunk_index, text, vector)
        → Embedding row upserted (ON CONFLICT DO UPDATE)

    Retrieval (Stage 5) — tools/retrieve_destinations.py
        → embed the user query → vector similarity search
        → SELECT ... ORDER BY vector <=> ? LIMIT k
        → returns top-k Embedding.text values to the agent

WHY COMPOSITE UNIQUE KEY ON (source, chunk_index)
---------------------------------------------------
Idempotent upserts: re-ingesting the same document replaces the existing
embedding vector rather than creating a duplicate.  The deterministic ID
`{source}_{chunk_index}` used in ingest.py maps to this key.

WHY Vector(EMBED_DIM) AND NOT A HARD-CODED 768
------------------------------------------------
`Settings.embed_dim` drives the dimension.  The value 768 matches
`nomic-embed-text`.  If the embedding model ever changes, an Alembic
migration drops and recreates the vector column with the new dimension.
This constant is read at migration time via env.py, not at ORM class
definition time, to avoid a circular import.

WHY THIS IS IN Stage 2 MODELS BUT IMPLEMENTED IN Stage 4
----------------------------------------------------------
The model is declared now so the first Alembic migration creates the full
schema in one transaction (including `CREATE EXTENSION vector`).  The
application code that uses this model (rag/store.py, tools/retrieve) is
wired in Stage 4.

NOTE: The `Vector` type requires the pgvector extension to be installed in
Postgres BEFORE this table is created.  The first migration ensures this
with `op.execute("CREATE EXTENSION IF NOT EXISTS vector")`.
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
    source      : file or document identifier, e.g. "wikivoyage_kyoto.md"
    chunk_index : position of this chunk within `source` (0-based)
    text        : the raw chunk text — returned to the agent as context
    vector      : pgvector(768) embedding from nomic-embed-text
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

    # Vector dimension is fixed to 768 (nomic-embed-text output size).
    # Changing the embedding model requires an Alembic migration.
    vector: Mapped[list[float]] = mapped_column(
        Vector(768),
        nullable=False,
    )
