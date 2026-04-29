"""User ORM model — one row per registered account.

HOW THIS MODEL FITS INTO THE DATA FLOW
----------------------------------------
    POST /auth/signup
        → auth_service.register_user()
        → creates a User row (email lowercased, password bcrypt-hashed)
        → session.add(user) → session.commit()

    POST /auth/login
        → auth_service.authenticate()
        → SELECT * FROM users WHERE email = ? (via scalar_one_or_none)
        → verify_password(plain, user.password_hash)
        → create_access_token(user_id=user.id) → returns JWT

    Authenticated request
        → deps/auth.py: decode_access_token(token) → user_id
        → SELECT * FROM users WHERE id = ? → User row
        → injected into route handler as `current_user`

WHY EMAIL UNIQUENESS LIVES AT THE DB LEVEL
-------------------------------------------
Uniqueness is enforced both by the UniqueConstraint at the DB level AND by
a service-layer check that raises DomainValidationError before hitting the
DB.  The DB constraint is the definitive safety net: two concurrent requests
that both pass the service check cannot both succeed — one will get an
IntegrityError that the service catches and converts to DomainValidationError.

WHY password_hash IS NEVER LOGGED OR SERIALISED
-------------------------------------------------
The service layer passes only the hash string here.  `UserOut` (the Pydantic
response schema) does not include `password_hash` — FastAPI will never
serialise it.  Never log `user.password_hash` directly; use `user.id` instead.

WHY cascade="all, delete-orphan" ON runs
-----------------------------------------
Deleting a user cascades to their AgentRun rows, and each AgentRun cascades
to its ToolCall rows.  Without this, the FK constraint on AgentRun.user_id
would raise an IntegrityError on user deletion.  The cascade matches
real-world expectation: deleting an account deletes all conversation history.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.agent_run import AgentRun


class User(TimestampMixin, Base):
    """Registered user account.

    Columns
    -------
    id            : surrogate PK — never exposed to clients directly (JWT
                    carries it, but the client should not parse the JWT).
    email         : unique, lowercase-normalised before INSERT — serves as the
                    human-readable identity and login credential.
    password_hash : bcrypt output (60-char string).  NEVER store the
                    plaintext.  NEVER log this field.
    """

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        # Future-proof: add partial indexes here if needed.
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    email: Mapped[str] = mapped_column(
        String(320),  # RFC 5321 max email length
        nullable=False,
        index=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(60),  # bcrypt always produces a 60-char string
        nullable=False,
    )

    # One user → many runs; deleting the user deletes their runs (cascade).
    runs: Mapped[list[AgentRun]] = relationship(
        "AgentRun",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",  # default — don't auto-join on every user fetch
    )
