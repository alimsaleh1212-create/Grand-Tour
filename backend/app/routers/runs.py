"""Runs router — read-side history of agent runs.

ENDPOINTS
---------
    GET /runs          — list user's runs (newest first, limit 50)
    GET /runs/{run_id} — full detail with tool calls timeline
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.settings import get_settings
from app.deps.auth import CurrentUser
from app.deps.db import get_session
from app.schemas.chat import NotifyResponse, RunDetailOut, RunOut
from app.services import run_service
from app.webhook.publisher import maybe_publish

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


@router.post("/{run_id}/notify", response_model=NotifyResponse, status_code=status.HTTP_200_OK)
async def notify_run(
    run_id: int,
    request: Request,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NotifyResponse:
    """Send run result to Discord webhook configured in server settings.

    Requires DISCORD_WEBHOOK_URL to be set in server environment.
    Returns 400 if not configured. Returns 404 if run not found or
    belongs to a different user.
    """
    settings = get_settings()
    discord_url = settings.discord_webhook_url
    if not discord_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discord webhook not configured on this server.",
        )

    run = await run_service.get_run_for_user(session, user_id=user.id, run_id=run_id)
    if run is None:
        raise NotFoundError("Run not found.")

    question = run.question or ""
    answer = run.final_answer or ""

    await maybe_publish(
        url=discord_url,
        run_id=run_id,
        question=question,
        answer=answer,
        session_factory=request.app.state.SessionLocal,
    )

    # maybe_publish updates webhook_status on the run; read result from DB
    updated = await run_service.get_run_for_user(session, user_id=user.id, run_id=run_id)
    delivered = updated is not None and updated.webhook_status == "delivered"

    log.info(
        "runs.notify",
        extra={"run_id": run_id, "user_id": user.id, "delivered": delivered},
    )
    return NotifyResponse(status="sent" if delivered else "failed")
