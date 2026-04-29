-- PostgreSQL initialisation script executed by the official postgres Docker
-- image on first container start (any *.sql in /docker-entrypoint-initdb.d/).
--
-- Purpose:
--   Enable the pgvector extension so that the `vector` column type and cosine-
--   distance operators (<->, <=>, <#>) are available before Alembic runs its
--   first migration.
--
-- Why here rather than in a migration:
--   `CREATE EXTENSION` requires superuser privileges.  Running it in the init
--   script (which executes as the postgres superuser) avoids having to grant
--   elevated permissions to the application role.  The Alembic migration that
--   creates the `embeddings` table can then rely on the extension already being
--   present.
--
-- Safe to re-run: IF NOT EXISTS is idempotent.

CREATE EXTENSION IF NOT EXISTS vector;
