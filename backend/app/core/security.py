"""Password hashing + JWT helpers — the cryptographic core of authentication.

HOW THIS MODULE FITS INTO THE AUTH FLOW
-----------------------------------------
    Registration (POST /auth/signup):
        plain_password → hash_password() → User.password_hash (stored in DB)

    Login (POST /auth/login):
        plain_password + stored_hash → verify_password() → bool
        If True → create_access_token(user_id=user.id) → JWT string → client

    Authenticated request:
        Bearer <token> → decode_access_token() → {"sub": "42", "exp": ...}
        → user_id = int(payload["sub"]) → fetch User from DB

WHY bcrypt SPECIFICALLY
------------------------
bcrypt is slow BY DESIGN.  Each hash takes ~100ms at cost factor 12.
This means an attacker who dumps the password_hash column can only attempt
~10 passwords per second per CPU core (vs. millions/second with MD5/SHA).
The cost factor comes from `settings.bcrypt_rounds` (default 12) so we can
raise it as hardware gets faster without rewriting the code.

WHY constant-time comparison matters (verify_password)
--------------------------------------------------------
A naive `hash(plain) == stored_hash` leaks timing information: if the
comparison exits on the first differing byte, an attacker can measure
network latency to determine how many bytes they got right.
`bcrypt.checkpw()` uses a constant-time algorithm that always compares all
bytes regardless of where they differ.

WHY JWT (not sessions or opaque tokens)
-----------------------------------------
JWTs are stateless: the server verifies the signature locally without a DB
round-trip per request.  The trade-off is that tokens cannot be revoked
before expiry (sessions or a token denylist can, but add DB overhead).
For this project, a 60-minute TTL (from `settings.jwt_access_ttl_minutes`)
keeps the revocation window short enough without the complexity.

JWT PAYLOAD STRUCTURE
----------------------
{
    "sub":  "42",       # user_id as string (JWT spec says sub is a string)
    "iat":  1700000000, # issued-at (Unix epoch)
    "exp":  1700003600, # expiry = iat + jwt_access_ttl_minutes * 60
}

WHY sub IS A STRING
---------------------
The JWT RFC (7519) requires `sub` to be a StringOrURI.  Storing an integer
directly would be non-standard and may confuse other JWT libraries.  We
parse it back to int in decode_access_token().

SECURITY NOTE: NEVER log the plaintext password or the JWT string.
The returned token is a credential — treat it like a password.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.exceptions import AuthError
from app.core.settings import get_settings

logger = logging.getLogger(__name__)


def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt.

    Args:
        plain: The user-supplied password.  NEVER logged, never stored.

    Returns:
        60-character bcrypt hash string suitable for storage in
        User.password_hash.

    Note:
        The cost factor is read from settings.bcrypt_rounds (default 12).
        bcrypt internally generates and embeds a cryptographically random
        salt in the output — no separate salt management required.
    """
    settings = get_settings()
    encoded = plain.encode("utf-8")
    salt = bcrypt.gensalt(rounds=settings.bcrypt_rounds)
    return bcrypt.hashpw(encoded, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash.

    Uses bcrypt.checkpw() which is constant-time — see module docstring.

    Args:
        plain:  The user-supplied password from the login request.
        hashed: The stored bcrypt hash from User.password_hash.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(*, user_id: int) -> str:
    """Issue a signed JWT for the given user.

    Args:
        user_id: The User.id to embed in the token's `sub` claim.

    Returns:
        Encoded JWT string.  This string is a credential — NEVER log it.

    Raises:
        Nothing — JWT encoding with a known algorithm and a non-None secret
        cannot fail at runtime.
    """
    settings = get_settings()
    now = datetime.now(tz=timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_ttl_minutes),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT, returning the payload.

    Performs three checks automatically (via PyJWT):
        1. Signature validity — rejects tokens signed with a different secret.
        2. Expiry (`exp`) — rejects tokens whose expiry has passed.
        3. Algorithm — rejects tokens signed with a different algorithm
           (prevents the `alg=none` attack).

    Args:
        token: Raw JWT string from the Authorization: Bearer header.

    Returns:
        Decoded payload dict, e.g. {"sub": "42", "iat": ..., "exp": ...}.

    Raises:
        AuthError: On any decoding failure (expired, tampered, wrong alg).
    """
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError:
        # Log at DEBUG — expired tokens are routine; not an attack signal.
        logger.debug("auth.token_expired")
        raise AuthError("Token has expired.")
    except jwt.InvalidTokenError as exc:
        # Log at WARNING — invalid tokens may indicate replay or tamper.
        logger.warning("auth.token_invalid", extra={"reason": str(exc)})
        raise AuthError("Invalid token.")
    return payload
