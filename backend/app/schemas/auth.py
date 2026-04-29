"""Authentication request/response schemas.

HOW SCHEMAS FIT INTO THE REQUEST/RESPONSE FLOW
------------------------------------------------
    POST /auth/signup
        browser → SignupRequest (validated by FastAPI/Pydantic)
              → auth_service.register_user()
              → UserOut (serialised to JSON by FastAPI)

    POST /auth/login
        browser → LoginRequest (validated by FastAPI/Pydantic)
              → auth_service.authenticate()
              → AccessTokenResponse (serialised to JSON)

    Authenticated endpoint
        client receives AccessTokenResponse.access_token (a JWT string)
        client sends: Authorization: Bearer <access_token>

WHY PYDANTIC SCHEMAS ARE SEPARATE FROM ORM MODELS
---------------------------------------------------
The ORM `User` model has columns like `password_hash` that must NEVER
appear in HTTP responses.  A separate Pydantic schema (`UserOut`) gives
us an explicit allowlist of what the client may see.  Without this
separation, a future developer could accidentally add `password_hash`
to the `User` model and have it leak through serialisation.

WHY EmailStr (not str) FOR email
----------------------------------
`pydantic[email]` validates that the value is a syntactically valid email
address (RFC 5322).  It also normalises it: `User@Example.COM` becomes
`user@example.com`.  This normalisation lives at the schema boundary so
the service layer always receives a canonical email and can compare it
case-insensitively without extra work.

WHY password min_length=8 / max_length=128
-------------------------------------------
min_length=8: industry baseline (NIST SP 800-63B recommends ≥ 8 chars).
max_length=128: prevents DoS via extremely long passwords that are fed
    to bcrypt (bcrypt silently truncates inputs > 72 bytes, so a 10 KB
    password is no stronger than a 72-byte one but wastes CPU time).

WHY expires_in IN AccessTokenResponse
---------------------------------------
Clients that store the token can use `expires_in` to schedule a re-login
before the token actually expires, giving a smoother UX than a sudden 401.
The value matches `Settings.jwt_access_ttl_minutes * 60` (seconds).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupRequest(BaseModel):
    """Body for POST /auth/signup.

    email    : normalised to lowercase by Pydantic's EmailStr.
    password : validated length; hashed before storage by auth_service.
    """

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """Body for POST /auth/login."""

    email: EmailStr
    password: str


class AccessTokenResponse(BaseModel):
    """Returned by POST /auth/login on success.

    access_token : the JWT string the client stores and sends as
                   `Authorization: Bearer <token>`.
    token_type   : always "bearer" — required by the OAuth2 standard.
    expires_in   : seconds until the token expires (for client-side scheduling).
    """

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class UserOut(BaseModel):
    """Safe public representation of a User.

    model_config with from_attributes=True enables ORM mode: FastAPI can
    pass a SQLAlchemy User instance directly and Pydantic will read the
    attributes rather than dict keys.

    Fields deliberately EXCLUDED: password_hash (credential), updated_at
    (implementation detail), runs (not needed at signup/login).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    created_at: datetime
