"""Authentication service — signup, login, token issue.

HOW THIS MODULE FITS INTO THE APPLICATION LAYERS
--------------------------------------------------
Layer diagram for the auth flow:

    HTTP Request
         ↓
    routers/auth.py          ← declares HTTP shape (status codes, body models)
         ↓  calls
    services/auth_service.py ← orchestrates business logic (THIS FILE)
         ↓  calls
    core/security.py         ← cryptographic primitives (hash, verify, JWT)
    db/models/user.py        ← ORM model (SELECT / INSERT)
         ↓
    Postgres

FUNCTION RESPONSIBILITIES
--------------------------
register_user()
    1. Normalise email to lowercase.
    2. Check for existing user (SELECT … WHERE email = ?).
    3. If exists → raise DomainValidationError (router maps to HTTP 409).
    4. Hash the password with bcrypt.
    5. INSERT the new User row.
    6. Return the User ORM object (router wraps it in UserOut).

authenticate()
    1. Normalise email to lowercase.
    2. SELECT user WHERE email = ? (scalar_one_or_none).
    3. If no user found → verify_password() on a dummy hash (constant time).
       Then raise AuthError with SAME message as wrong-password case.
       This prevents user enumeration: the response time is indistinguishable
       whether the email doesn't exist or the password is wrong.
    4. If password wrong → raise AuthError.
    5. Issue JWT → return AccessTokenResponse.

WHY CONSTANT-TIME FALLBACK ON MISSING USER
-------------------------------------------
Without the dummy hash, a user enumeration attack works like this:
    - POST /auth/login {"email": "victim@example.com", "password": "wrong"}
    - If the email doesn't exist: response in ~1 ms (no bcrypt, fast SELECT)
    - If the email exists:        response in ~100 ms (bcrypt is slow)
The timing difference reveals whether an email is registered.
By running bcrypt.checkpw() against a dummy hash when the user is not found,
both paths take ~100 ms, defeating the timing side-channel.

COVERAGE NOTE
--------------
This file is the critical path — coverage target ≥ 95% per project guidelines.
Every branch (email collision, missing user, wrong password, success) is
exercised in tests/unit/test_auth_service.py.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError, DomainValidationError
from app.core.security import create_access_token, hash_password, verify_password
from app.core.settings import get_settings
from app.db.models.user import User
from app.schemas.auth import AccessTokenResponse, UserOut

logger = logging.getLogger(__name__)

# Dummy hash used to run bcrypt even when the user is not found.
# This prevents the timing side-channel described in the module docstring.
# The value is a valid bcrypt hash (of the string "dummy") — checkpw will
# always return False against it, but it takes the same ~100 ms to compute.
_DUMMY_HASH = "$2b$12$KIX/7YMb8HQxK5.8R7kKj.4j2QnFm2gLqxW3nFjLXZXq1Lx1s73Aq"


async def register_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
) -> UserOut:
    """Register a new user account.

    Args:
        session:  An open AsyncSession (injected by the get_session dep).
        email:    User-supplied email.  Normalised to lowercase here.
        password: Plaintext password.  Hashed before storage; NEVER logged.

    Returns:
        UserOut with the new user's id, email, created_at.

    Raises:
        DomainValidationError: If the email is already registered.
            (Router maps this to HTTP 409 Conflict.)

    Flow:
        email normalise → duplicate check → hash → INSERT → UserOut
    """
    email = email.lower().strip()

    # Duplicate-email check — service layer catches it before the DB
    # constraint does, giving a clearer error message.
    result = await session.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()
    if existing is not None:
        # Raise DomainValidationError rather than AuthError so the router
        # maps this to 409 Conflict, not 401 Unauthorized.
        raise DomainValidationError("Email already registered.")

    password_hash = hash_password(password)
    user = User(email=email, password_hash=password_hash)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    logger.info("auth.signup", extra={"user_id": user.id})
    return UserOut.model_validate(user)


async def authenticate(
    session: AsyncSession,
    *,
    email: str,
    password: str,
) -> AccessTokenResponse:
    """Verify credentials and issue a JWT access token.

    Args:
        session:  An open AsyncSession.
        email:    User-supplied email.  Normalised to lowercase.
        password: Plaintext password to verify against the stored hash.

    Returns:
        AccessTokenResponse with the JWT and its expiry in seconds.

    Raises:
        AuthError: If the email is not registered OR the password is wrong.
            Both cases raise the SAME error (anti-enumeration).
            (Router maps AuthError to HTTP 401.)

    Flow:
        email normalise → SELECT → constant-time verify → JWT → response
    """
    email = email.lower().strip()
    settings = get_settings()

    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        # Run bcrypt against a dummy hash to prevent timing side-channel.
        # verify_password always returns False here; we raise afterward.
        verify_password(password, _DUMMY_HASH)
        logger.warning("auth.login_fail", extra={"reason": "unknown_email"})
        raise AuthError("Invalid email or password.")

    if not verify_password(password, user.password_hash):
        logger.warning(
            "auth.login_fail", extra={"user_id": user.id, "reason": "wrong_password"}
        )
        raise AuthError("Invalid email or password.")

    token = create_access_token(user_id=user.id)
    expires_in = settings.jwt_access_ttl_minutes * 60

    logger.info("auth.login_success", extra={"user_id": user.id})
    return AccessTokenResponse(
        access_token=token,
        expires_in=expires_in,
    )
