"""ORM models package — importing this registers all models on Base.metadata.

WHY THESE IMPORTS MUST EXIST HERE
-----------------------------------
Alembic's autogenerate inspects `Base.metadata` to know which tables exist.
`Base.metadata` is only populated when the ORM class bodies execute (i.e.
when the module containing the class is imported).

The `alembic/env.py` file does:
    from app.db.models import *  # noqa: F401, F403

This single import causes all four model files to be evaluated, which
registers all four tables on `Base.metadata`.  Without this package-level
import, autogenerate would produce an empty migration.

IMPORT ORDER
-------------
Order matters because of FK references:
    User     — no FK dependencies
    AgentRun — FK to users
    ToolCall — FK to agent_runs
    Embedding — no FK dependencies (standalone RAG table)
"""

from app.db.models.agent_run import AgentRun as AgentRun
from app.db.models.embedding import Embedding as Embedding
from app.db.models.tool_call import ToolCall as ToolCall
from app.db.models.user import User as User

__all__ = ["User", "AgentRun", "ToolCall", "Embedding"]
