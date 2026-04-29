"""Current-user dependency — decodes JWT and returns the authenticated User.

HOW THIS FITS INTO THE REQUEST LIFECYCLE
------------------------------------------
For every route that declares:

    user: Annotated[User, Depends(current_user)]

FastAPI resolves the dependency chain:
    1. bearer_scheme(request) extracts the Authorization header.
    2. get_session(request) opens an AsyncSession (see deps/db.py).
    3. current_user(creds, session):
        a. If no credentials → raise AuthError → 401.
        b. decode_access_token(token) → payload.
        c. user_id = int(payload["sub"]).
        d. SELECT * FROM users WHERE id = user_id.
        e. If not found → raise AuthError → 401.
        f. Return the User ORM object.

WHY auto_error=False ON HTTPBearer
------------------------------------
`HTTPBearer(auto_error=True)` would return a generic 403 if the header is
absent or malformed.  With `auto_error=False`, the scheme returns `None`
instead of raising, letting us raise `AuthError` (→ 401) consistently via
our own exception handler — the client sees the same error format for ALL
auth failures.

WHY GENERIC 401 DETAIL (not "user not found" vs "token invalid")
-----------------------------------------------------------------
Distinguishing between "token decoding failed" and "user ID in token doesn't
exist in DB" leaks information about which IDs are valid.  A single generic
message ("Authentication required.") covers all auth failure modes.

SECURITY: Do NOT log the raw token.  Log only the user_id AFTER a successful
decode, or the generic failure reason.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError
from app.core.security import decode_access_token
from app.db.models.user import User
from app.deps.db import get_session

logger = logging.getLogger(__name__)

# auto_error=False: returns None when header is absent instead of raising 403.
# Our current_user raises AuthError (→ 401) for a consistent client experience.
bearer_scheme = HTTPBearer(auto_error=False)


async def current_user(
    creds: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """Decode the Bearer JWT and return the authenticated User ORM object.

    All failure modes raise AuthError, which the exception handler in
    app/main.py converts to HTTP 401 {"detail": "Authentication required."}.

    Args:
        creds:   The parsed Authorization header, or None if absent.
        session: An open AsyncSession from get_session().

    Returns:
        The User ORM instance for the authenticated user.

    Raises:
        AuthError: On any auth failure (missing header, invalid token, user
                   not found in DB, etc.).

    Usage in a route:
        @router.get("/me")
        async def get_me(user: Annotated[User, Depends(current_user)]) -> UserOut:
            return UserOut.model_validate(user)
    """
    if creds is None:
        raise AuthError("Missing Authorization header.")

    # decode_access_token raises AuthError on expiry or tampering.
    payload = decode_access_token(creds.credentials)

    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError):
        raise AuthError("Malformed token payload.")

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning("auth.user_not_found", extra={"user_id": user_id})
        raise AuthError("User not found.")

    return user


# Convenience alias — routes annotate with this instead of the full Depends().
# Usage:  async def my_route(user: CurrentUser) -> ...:
CurrentUser = Annotated[User, Depends(current_user)]
