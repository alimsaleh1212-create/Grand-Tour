"""Database layer — async SQLAlchemy + pgvector.

Modules:
    base.py      Declarative `Base` and shared mixins (id, timestamps).
    session.py   `create_async_engine`, `async_sessionmaker`, lifespan
                 plumbing, `get_session` async-generator dependency.
    models/      One file per ORM entity (User, AgentRun, ToolCall,
                 Embedding). The pgvector column lives on Embedding only.

Design notes (per project brief):
    * Every DB call is async (SQLAlchemy 2.x async session, asyncpg driver).
    * The engine is a process-wide singleton constructed in the FastAPI
      lifespan handler; route handlers depend on a session via
      `Depends(get_session)`. Tests override that dep with an in-memory
      session bound to a transactional rollback.
    * Migrations are managed by Alembic; the pgvector extension is created
      in the very first revision before any vector(N) columns appear.
"""
