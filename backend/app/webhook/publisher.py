"""Webhook publisher — async POST with retry, timeout, structured logging.

NEVER raises. Webhook failure is logged and the run's webhook_status is
updated to "failed" — it never breaks the user-facing response.

PUBLIC SURFACE
--------------
    async def publish(url, payload, *, timeout_seconds, max_retries) -> bool
    async def maybe_publish(url, run_id, question, answer, session_factory)
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from app.webhook.adapters import build_payload

log = logging.getLogger(__name__)


async def publish(
    url: str,
    payload: dict[str, object],
    *,
    timeout_seconds: float = 5.0,
    max_retries: int = 1,
) -> bool:
    """POST payload to url with tenacity-style retry and timeout.

    Args:
        url: Webhook destination URL.
        payload: JSON body to deliver.
        timeout_seconds: Per-attempt timeout.
        max_retries: Total additional attempts after the first (so 1 = 2 total).

    Returns:
        True on successful delivery (2xx), False on all failures.
    """
    attempts = max_retries + 1
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        for attempt in range(attempts):
            backoff = 2**attempt  # 1s, 2s, 4s …
            try:
                resp = await client.post(url, json=payload)
                if resp.is_success:
                    log.info(
                        "webhook.delivered",
                        extra={
                            "url": _redact(url),
                            "status": resp.status_code,
                            "attempt": attempt + 1,
                        },
                    )
                    return True

                log.warning(
                    "webhook.http_error",
                    extra={
                        "url": _redact(url),
                        "status": resp.status_code,
                        "attempt": attempt + 1,
                    },
                )

            except httpx.TimeoutException:
                log.warning(
                    "webhook.timeout",
                    extra={"url": _redact(url), "attempt": attempt + 1},
                )
            except httpx.RequestError as exc:
                log.warning(
                    "webhook.transport_error",
                    extra={
                        "url": _redact(url),
                        "error": str(exc),
                        "attempt": attempt + 1,
                    },
                )

            if attempt < attempts - 1:
                await asyncio.sleep(backoff)

    log.error(
        "webhook.failed",
        extra={"url": _redact(url), "total_attempts": attempts},
    )
    return False


async def maybe_publish(
    url: str,
    run_id: int,
    question: str,
    answer: str,
    session_factory: object,
) -> None:
    """Build the right payload and attempt delivery; update run webhook_status.

    Called via FastAPI BackgroundTasks — runs after the response is sent.
    Never raises; failure is logged and persisted.

    Args:
        url: Webhook destination.
        run_id: AgentRun PK for status update.
        question: Original question (for the payload).
        answer: Final answer (for the payload).
        session_factory: async_sessionmaker from app.state.SessionLocal.
    """
    from app.core.settings import get_settings
    from app.services import run_service

    settings = get_settings()
    payload = build_payload(url, question, answer, run_id)
    delivered = await publish(
        url,
        payload,
        timeout_seconds=settings.webhook_timeout_seconds,
        max_retries=settings.webhook_max_retries,
    )

    # Update webhook_status on the run row
    try:
        async with session_factory() as session:
            await run_service.finalise_run(
                session,
                run_id=run_id,
                final_answer=answer,
                total_tokens_cheap=0,
                total_tokens_strong=0,
                webhook_status="delivered" if delivered else "failed",
            )
            await session.commit()
    except Exception:
        log.exception("webhook.status_update_failed", extra={"run_id": run_id})


def _redact(url: str) -> str:
    """Remove everything after '?' and truncate to avoid leaking tokens."""
    return url.split("?")[0][:80]
