"""Initial schema — pgvector extension + all tables.

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-04-28 00:00:00

HOW TO READ THIS MIGRATION
----------------------------
This is the first migration.  It creates the full schema in one transaction:

    1. CREATE EXTENSION IF NOT EXISTS vector
       Required before any column can use the pgvector `vector(N)` type.
       IF NOT EXISTS makes this idempotent — safe to re-run.

    2. CREATE TABLE users
       Foundation table — all other tables FK to this one.

    3. CREATE TABLE agent_runs
       One row per chat interaction.  FK → users.id.

    4. CREATE TABLE tool_calls
       One row per tool invocation within a run.  FK → agent_runs.id.

    5. CREATE TABLE embeddings
       RAG knowledge chunks with pgvector(768) column.  No FK.

HOW TO RUN
-----------
    # From backend/
    alembic upgrade head     # applies this migration
    alembic downgrade -1     # reverts this migration (drops all tables)

DOWNGRADE SAFETY
-----------------
Downgrade drops all tables (CASCADE).  This is correct for the initial
migration — there is nothing to preserve.  Future migrations use targeted
ALTER TABLE / DROP COLUMN operations.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# Revision identifiers used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Apply the initial schema."""

    # ── 1. pgvector extension ──────────────────────────────────────────────────
    # Must run BEFORE any table with a vector(N) column is created.
    # IF NOT EXISTS: idempotent; safe if the extension was installed manually.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # ── 2. users ──────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(60), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)

    # ── 3. agent_runs ─────────────────────────────────────────────────────────
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("final_answer", sa.Text(), nullable=True),
        sa.Column("total_tokens_cheap", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens_strong", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "cost_usd",
            sa.Numeric(precision=10, scale=6),
            nullable=False,
            server_default="0",
        ),
        sa.Column("webhook_status", sa.String(16), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_agent_runs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_runs")),
    )
    op.create_index(
        op.f("ix_agent_runs_user_id"), "agent_runs", ["user_id"], unique=False
    )

    # ── 4. tool_calls ─────────────────────────────────────────────────────────
    op.create_table(
        "tool_calls",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("args_json", JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_json", JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["agent_runs.id"],
            name=op.f("fk_tool_calls_run_id_agent_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tool_calls")),
    )
    op.create_index(
        op.f("ix_tool_calls_run_id"), "tool_calls", ["run_id"], unique=False
    )

    # ── 5. embeddings (pgvector) ───────────────────────────────────────────────
    # The vector(768) type is available now that the pgvector extension is loaded.
    # We use raw SQL for the vector column because SQLAlchemy's generic DDL
    # doesn't know about the pgvector type; it must be spelled out literally.
    op.create_table(
        "embeddings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(512), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_embeddings")),
        sa.UniqueConstraint(
            "source",
            "chunk_index",
            name="uq_embeddings_source_chunk",
        ),
    )
    # Add the vector column separately with raw SQL — Alembic DDL helpers
    # don't know the `vector` type; pgvector registers it as a Postgres type.
    op.execute("ALTER TABLE embeddings ADD COLUMN vector vector(768) NOT NULL;")
    op.create_index(
        op.f("ix_embeddings_source"), "embeddings", ["source"], unique=False
    )
    # ivfflat index for approximate nearest-neighbour search (cosine metric).
    # lists=100 is a reasonable default for datasets up to ~1M rows.
    # This index speeds up the SELECT ... ORDER BY vector <=> ? LIMIT k query.
    op.execute(
        "CREATE INDEX ix_embeddings_vector_cosine "
        "ON embeddings USING ivfflat (vector vector_cosine_ops) WITH (lists = 100);"
    )


def downgrade() -> None:
    """Revert the initial schema — drops all tables and the extension."""
    op.drop_table("embeddings")
    op.drop_table("tool_calls")
    op.drop_table("agent_runs")
    op.drop_table("users")
    # NOTE: We intentionally do NOT drop the vector extension here.
    # The extension may have been installed by a database admin (not this
    # app), and other databases on the same Postgres instance may use it.
    # If you need to drop it, do so manually: DROP EXTENSION IF EXISTS vector;
