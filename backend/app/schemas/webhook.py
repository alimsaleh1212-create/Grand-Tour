"""Outbound webhook payload schema.

Implemented in Stage 8.

Public surface (planned):
    class WebhookPayload(BaseModel):
        run_id: int
        question: str
        answer: str
        tools_fired: list[str]
        timestamp: datetime

    Adapter functions in `webhook.adapters` translate this into the
    channel-specific format (Discord embed JSON / Slack blocks / etc.).
"""
