"""Webhook orchestration — picks an adapter, hands off to publisher.

Implemented in Stage 8.

Public surface (planned):
    async def deliver_run_summary(
        *,
        run: AgentRun,
        target_url: str | None,
        adapter: Literal["discord", "slack"] = "discord",
    ) -> WebhookDeliveryStatus: ...

Behaviour:
    * Builds a `WebhookPayload` from the AgentRun + its ToolCalls.
    * Routes to the chosen adapter (Discord by default).
    * Delegates the actual HTTP call to `webhook.publisher.publish()`,
      which handles timeout + retry + structured failure logging.
    * Persists the final delivery status on AgentRun.webhook_status.
    * NEVER raises into the route handler — webhook failure must not break
      the user-facing response.
"""
