"""Add section, destination, source_url columns to embeddings.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-29 00:00:00

WHY THIS MIGRATION
-------------------
The initial schema stored only (source, chunk_index, text, vector).
Stage 4's section-aware chunker now produces richer metadata per chunk:

    section     — H2 header label so the retrieve tool can cite the exact
                  section of a travel guide (e.g. "Practical Information").

    destination — Human-readable destination name extracted at ingest time
                  (e.g. "Kyoto").  Stored as a top-level column so the
                  classify_style tool can receive a clean machine-derived
                  destination name without parsing prose.

    source_url  — Origin website base URL for deterministic citations
                  (e.g. "https://en.wikivoyage.org/").  The retrieve tool
                  returns this as a structured field — never buried in text.

All three columns are NOT NULL with an empty-string default so that:
    1. Existing rows (ingested before this migration) remain valid.
    2. Application code never has to handle None for these fields.

HOW TO RUN
-----------
    # From backend/
    alembic upgrade head     # adds the three columns
    alembic downgrade -1     # drops the three columns (reverts to a1b2c3d4e5f6)

AFTER RUNNING
--------------
Re-run `uv run python -m rag.scripts.ingest` to populate the new columns
for all existing rows.  The ON CONFLICT DO UPDATE clause in store.upsert()
will fill section, destination, and source_url on every existing row.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Add section, destination, source_url to embeddings."""
    op.add_column(
        "embeddings",
        sa.Column(
            "section",
            sa.String(256),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "embeddings",
        sa.Column(
            "destination",
            sa.String(256),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "embeddings",
        sa.Column(
            "source_url",
            sa.String(512),
            nullable=False,
            server_default="",
        ),
    )


def downgrade() -> None:
    """Remove the three metadata columns."""
    op.drop_column("embeddings", "source_url")
    op.drop_column("embeddings", "destination")
    op.drop_column("embeddings", "section")
