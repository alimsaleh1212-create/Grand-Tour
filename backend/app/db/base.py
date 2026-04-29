"""SQLAlchemy declarative base + shared column mixins.

HOW THIS MODULE FITS INTO THE ORM LAYER
-----------------------------------------
Every ORM model in `app/db/models/` inherits from `Base`.  The `Base` class
carries a single `MetaData` object that Alembic introspects via
`target_metadata` in `alembic/env.py` to autogenerate migrations.

Importing `Base` implicitly means:
    * All mapped tables share the same metadata registry.
    * Alembic sees every model by importing `app.db.models` (which imports
      each model file, causing them to register on Base.metadata).

STARTUP FLOW POSITION
----------------------
This module is imported at startup via `app.db.models.__init__`, which is
imported by `alembic/env.py` (for migrations) and by any route/service that
touches the DB.  No connections are opened here — that happens in lifespan.

WHY TimestampMixin INSTEAD OF REPEATING COLUMNS
------------------------------------------------
`created_at` and `updated_at` appear on every entity.  A mixin avoids
repetition AND ensures the server default (func.now()) is wired consistently.
The mixin is a plain class (not a model) — SQLAlchemy's MappedAsDataclass
protocol treats mixin columns as if they were declared directly on the
inheriting class.

NOTE on `__abstract__ = True`
-------------------------------
Setting `__abstract__ = True` on `Base` tells SQLAlchemy NOT to create a
table named "base".  Every concrete subclass gets its own table.  Without
this flag, SQLAlchemy would expect a `base` table in the DB.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Root declarative base shared by all ORM models.

    Inheriting from `DeclarativeBase` (SQLAlchemy 2.0 style) gives us:
      - Automatic `__tablename__` from the class name (lowercase) unless
        overridden (we always override explicitly for clarity).
      - `Base.metadata` — the single registry Alembic reads.
      - Full type-checker support via `Mapped[T]` annotations.
    """

    pass


class TimestampMixin:
    """Adds `created_at` and `updated_at` columns to any ORM model.

    HOW TO USE
    -----------
    class User(TimestampMixin, Base):
        __tablename__ = "users"
        ...

    WHY server_default INSTEAD OF default
    ---------------------------------------
    `server_default=func.now()` means the DB generates the timestamp using
    `NOW()` at INSERT time.  This is safer than a Python `default=datetime.utcnow`
    because:
      1. The value is guaranteed to be in the DB's timezone (UTC on Postgres).
      2. Bulk inserts that bypass Python ORM still get correct timestamps.
      3. The clock source is the DB, not the app server — avoids clock skew
         in multi-replica deployments.

    WHY `onupdate=func.now()` FOR updated_at
    ------------------------------------------
    SQLAlchemy calls this on every `session.flush()` that modifies the row,
    so `updated_at` is always the real last-modified timestamp without any
    application code tracking it manually.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
