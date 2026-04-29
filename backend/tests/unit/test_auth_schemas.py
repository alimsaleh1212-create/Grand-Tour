"""Unit tests for app/schemas/auth.py — no DB required.

WHAT IS TESTED HERE
--------------------
1. SignupRequest: accepts valid email + password; rejects too-short password,
   too-long password, and malformed email.
2. LoginRequest: basic shape validation.
3. AccessTokenResponse: correct defaults.
4. UserOut: from_attributes=True works with a mock ORM object.

WHY SCHEMA TESTS MATTER
------------------------
Pydantic schemas are the outermost safety net — they run BEFORE any service
code.  If a schema lets through invalid data (e.g. a 3-char password), the
service must defensively re-validate, which violates the "trust internal code"
principle.  These tests lock in the schema contract so service code can be
written without defensive re-validation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.auth import AccessTokenResponse, LoginRequest, SignupRequest, UserOut


class TestSignupRequest:
    def test_valid_signup(self) -> None:
        req = SignupRequest(email="user@example.com", password="strongpass")
        assert req.email == "user@example.com"

    def test_email_domain_is_normalised(self) -> None:
        """Pydantic's EmailStr lowercases the domain portion (RFC 5321).

        The local part (before @) is technically case-sensitive per RFC, so
        EmailStr preserves it. The service layer calls email.lower() anyway,
        so the DB always stores a fully-lowercase address.
        """
        req = SignupRequest(email="user@EXAMPLE.COM", password="strongpass")
        assert req.email == "user@example.com"

    def test_password_too_short_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SignupRequest(email="a@b.com", password="short")
        errors = exc_info.value.errors()
        assert any("password" in str(e["loc"]) for e in errors)

    def test_password_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SignupRequest(email="a@b.com", password="x" * 129)

    def test_password_at_min_length(self) -> None:
        req = SignupRequest(email="a@b.com", password="12345678")
        assert len(req.password) == 8

    def test_password_at_max_length(self) -> None:
        req = SignupRequest(email="a@b.com", password="x" * 128)
        assert len(req.password) == 128

    def test_invalid_email_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SignupRequest(email="not-an-email", password="validpass123")

    def test_missing_email_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SignupRequest(password="validpass123")  # type: ignore[call-arg]

    def test_missing_password_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SignupRequest(email="a@b.com")  # type: ignore[call-arg]


class TestLoginRequest:
    def test_valid_login(self) -> None:
        req = LoginRequest(email="user@example.com", password="anything")
        assert req.email == "user@example.com"

    def test_invalid_email_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LoginRequest(email="bad-email", password="anything")


class TestAccessTokenResponse:
    def test_defaults(self) -> None:
        resp = AccessTokenResponse(access_token="tok123", expires_in=3600)
        assert resp.token_type == "bearer"

    def test_fields(self) -> None:
        resp = AccessTokenResponse(access_token="abc", expires_in=60)
        assert resp.access_token == "abc"
        assert resp.expires_in == 60


class TestUserOut:
    def test_from_orm_object(self) -> None:
        """from_attributes=True allows constructing UserOut from an ORM-like object."""
        fake_user = SimpleNamespace(
            id=7,
            email="test@example.com",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        out = UserOut.model_validate(fake_user)
        assert out.id == 7
        assert out.email == "test@example.com"

    def test_password_hash_not_in_fields(self) -> None:
        """Ensure password_hash cannot be serialised via UserOut."""
        fields = set(UserOut.model_fields.keys())
        assert "password_hash" not in fields
