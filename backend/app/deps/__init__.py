"""FastAPI Depends() providers.

Per the brief: "Stop instantiating clients inside route handlers. Your LLM
client, database session, embedding model, agent executor, and current user
are all dependencies — declare them with `Depends()` and let FastAPI wire
them in."

Modules:
    db.py            get_session — async SQLAlchemy session per request.
    auth.py          current_user — decodes JWT, fetches user.
    agent.py         get_agent — returns the LangGraph executor with
                     bound dependencies (LLMs, vector store, ML model).
    ml_model.py      get_classifier — yields the lifespan-loaded joblib.
    vector_store.py  get_vector_store — yields the live Qdrant/pgvector
                     handle.

Tests override these via FastAPI's `app.dependency_overrides` mechanism.
"""
