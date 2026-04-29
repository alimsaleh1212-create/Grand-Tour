"""Authentication router — signup and login endpoints.

HOW THIS ROUTER FITS INTO THE REQUEST FLOW
--------------------------------------------
    POST /auth/signup
        1. FastAPI validates the body as SignupRequest (Pydantic).
        2. get_session() opens an AsyncSession.
        3. register_user(session, email, password) runs.
           - Raises DomainValidationError → 422 if email taken.
        4. FastAPI serialises UserOut → HTTP 201 Created.

    POST /auth/login
        1. FastAPI validates LoginRequest.
        2. authenticate(session, email, password) runs.
           - Raises AuthError → 401 on wrong credentials.
        3. FastAPI serialises AccessTokenResponse → HTTP 200.

DESIGN DECISIONS
-----------------
* Routes contain ZERO business logic — they only declare the HTTP shape
  (status codes, schema mapping) and delegate to the service layer.
  This matches CLAUDE.md §14: "Services own business logic; routers own HTTP."

* status_code=201 on signup: RFC 9110 says 201 Created is the correct
  status for a resource-creation endpoint that returns the new resource.
  Using 200 would be technically incorrect (200 = "OK, here's what you
  asked for", not "I created something").

* No 404 branch on login: we deliberately do NOT return 404 for unknown
  emails.  Both "email unknown" and "password wrong" paths return 401 with
  an identical body — the service layer enforces this.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps.db import get_session
from app.schemas.auth import AccessTokenResponse, LoginRequest, SignupRequest, UserOut
from app.services import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
    description=(
        "Creates a user account. Returns the new user's public profile. "
        "Returns 422 if the email is already registered."
    ),
)
async def signup(
    body: SignupRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserOut:
    """Register a new user.

    Delegates entirely to auth_service.register_user().
    All validation and error handling lives there.
    """
    return await auth_service.register_user(
        session,
        email=body.email,
        password=body.password,
    )


@router.post(
    "/login",
    response_model=AccessTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Log in and receive an access token",
    description=(
        "Validates credentials and issues a JWT access token. "
        "Returns 401 on wrong email or password (same response for both "
        "— prevents user enumeration)."
    ),
)
async def login(
    body: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AccessTokenResponse:
    """Authenticate a user and issue a JWT.

    Delegates entirely to auth_service.authenticate().
    """
    return await auth_service.authenticate(
        session,
        email=body.email,
        password=body.password,
    )
