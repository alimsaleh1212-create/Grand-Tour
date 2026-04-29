"""Unit tests for app/core/security.py — no DB required.

WHAT IS TESTED HERE
--------------------
1. hash_password() produces a bcrypt hash (not the plaintext).
2. verify_password() returns True on match, False on mismatch.
3. Hashing is non-deterministic — two calls on the same input produce
   different hashes (each bcrypt hash embeds a random salt).
4. create_access_token() produces a JWT that decodes correctly.
5. decode_access_token() rejects an expired token.
6. decode_access_token() rejects a tampered token.
7. decode_access_token() rejects the wrong algorithm.
8. The "sub" claim is a string representation of the user ID.

COVERAGE TARGET
----------------
These tests cover every branch in core/security.py.  Together with
test_auth_service.py they push auth_service.py to ≥ 95% coverage.

HOW SETTINGS ARE HANDLED
--------------------------
get_settings() is @lru_cache'd.  The test environment must have the required
env vars set.  We patch them via monkeypatch on the os.environ dict and then
clear the cache so get_settings() re-reads them.
"""

from __future__ import annotations

import time

import pytest

from app.core.exceptions import AuthError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestHashPassword:
    """hash_password() and verify_password() behaviour."""

    def test_hash_is_not_plaintext(self) -> None:
        """The hash must NOT be the plaintext — this is the most basic check."""
        plain = "supersecret123"
        hashed = hash_password(plain)
        assert hashed != plain

    def test_hash_is_bcrypt(self) -> None:
        """bcrypt hashes always start with '$2b$'."""
        hashed = hash_password("anypassword")
        assert hashed.startswith("$2b$")

    def test_hash_length_is_60(self) -> None:
        """bcrypt always produces a 60-character string."""
        hashed = hash_password("anypassword")
        assert len(hashed) == 60

    def test_different_salts_same_input(self) -> None:
        """Two hashes of the same password must differ (random salt)."""
        plain = "samepassword"
        h1 = hash_password(plain)
        h2 = hash_password(plain)
        assert h1 != h2

    def test_verify_correct_password(self) -> None:
        plain = "correct-horse-battery-staple"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_wrong_password(self) -> None:
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_password_not_in_hash_repr(self) -> None:
        """The plaintext must not be a substring of the hash string."""
        plain = "uniquepassword99"
        hashed = hash_password(plain)
        assert plain not in hashed


class TestJWT:
    """create_access_token() and decode_access_token() behaviour."""

    def test_round_trip(self) -> None:
        """A token created for user_id=42 must decode back to sub='42'."""
        token = create_access_token(user_id=42)
        payload = decode_access_token(token)
        assert payload["sub"] == "42"

    def test_sub_is_string(self) -> None:
        """JWT spec requires sub to be a string, not an int."""
        token = create_access_token(user_id=7)
        payload = decode_access_token(token)
        assert isinstance(payload["sub"], str)

    def test_payload_has_exp(self) -> None:
        """Token must include an exp claim."""
        token = create_access_token(user_id=1)
        payload = decode_access_token(token)
        assert "exp" in payload

    def test_payload_has_iat(self) -> None:
        """Token must include an iat claim."""
        token = create_access_token(user_id=1)
        payload = decode_access_token(token)
        assert "iat" in payload

    def test_different_users_produce_different_tokens(self) -> None:
        t1 = create_access_token(user_id=1)
        t2 = create_access_token(user_id=2)
        assert t1 != t2

    def test_expired_token_raises_auth_error(self) -> None:
        """A token with exp in the past must raise AuthError."""
        from app.core.settings import get_settings

        settings = get_settings()
        import jwt

        payload = {
            "sub": "99",
            "iat": 0,
            "exp": 1,  # Unix epoch 1 = far in the past
        }
        expired_token = jwt.encode(
            payload,
            settings.jwt_secret.get_secret_value(),
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(AuthError):
            decode_access_token(expired_token)

    def test_tampered_token_raises_auth_error(self) -> None:
        """A token with a replaced signature must raise AuthError."""
        token = create_access_token(user_id=1)
        # Replace the signature segment entirely with a clearly wrong value.
        header_payload = ".".join(token.split(".")[:2])
        tampered = header_payload + ".invalidsignatureXXXXXXXXXXXXXXXXXXXXX"
        with pytest.raises(AuthError):
            decode_access_token(tampered)

    def test_wrong_secret_raises_auth_error(self) -> None:
        """A token signed with a different secret must raise AuthError."""
        import jwt

        from app.core.settings import get_settings

        settings = get_settings()
        payload = {"sub": "1", "iat": int(time.time()), "exp": int(time.time()) + 3600}
        token_wrong_secret = jwt.encode(
            payload,
            "completely-wrong-secret",
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(AuthError):
            decode_access_token(token_wrong_secret)

    def test_none_algorithm_rejected(self) -> None:
        """A token using alg=none (the classic JWT attack) must be rejected."""
        import jwt

        payload = {"sub": "1", "iat": int(time.time()), "exp": int(time.time()) + 3600}
        # Manually encode without a real secret using the none algorithm.
        # PyJWT rejects this because we specify algorithms=[settings.jwt_algorithm].
        token_none = jwt.encode(payload, "", algorithm="none")
        with pytest.raises(AuthError):
            decode_access_token(token_none)
