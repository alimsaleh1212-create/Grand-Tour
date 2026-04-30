"""Runs router — read-side history of agent runs.

ENDPOINTS
---------
    GET /runs          — list user's runs (newest first, limit 50)
    GET /runs/{run_id} — full detail with tool calls timeline
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.deps.auth import CurrentUser
from app.deps.db import get_session
from app.schemas.chat import RunDetailOut, RunOut
from app.services import run_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=list[RunOut])
async def list_runs(
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[RunOut]:
    """Return the authenticated user's runs, newest first."""
    runs = await run_service.list_runs_for_user(session, user_id=user.id)
    return [RunOut.model_validate(r) for r in runs]


@router.get("/{run_id}", response_model=RunDetailOut)
async def get_run(
    run_id: int,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RunDetailOut:
    """Return one run with its full tool-call timeline.

    Returns 404 if the run does not exist OR belongs to a different user
    (cross-user isolation — do not leak existence).
    """
    run = await run_service.get_run_for_user(
        session, user_id=user.id, run_id=run_id
    )
    if run is None:
        raise NotFoundError("Run not found.")
    return RunDetailOut.model_validate(run)
