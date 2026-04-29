"""Webhook publisher — async POST with retry, timeout, structured logging.

Implemented in Stage 8.

Public surface (planned):
    @dataclass
    class WebhookDeliveryStatus:
        delivered: bool
        attempts: int
        final_status_code: int | None
        error_kind: str | None  # timeout | http_error | transport_error | none

    async def publish(
        url: HttpUrl,
        payload: dict,
        *,
        client: httpx.AsyncClient,
        timeout_seconds: float,
        max_retries: int,
    ) -> WebhookDeliveryStatus: ...

Behaviour:
    * Timeout per attempt = `Settings.webhook_timeout_seconds`.
    * Retry budget = `Settings.webhook_max_retries`. Backoff = 1s, 2s, 4s.
    * On final failure: `logger.error("Webhook delivery failed", extra={
      "url": redact(url), "attempts": ...})` and return delivered=False.
    * NEVER raises. The webhook failing must not break the user-facing
      response — that's an explicit project requirement.
"""
