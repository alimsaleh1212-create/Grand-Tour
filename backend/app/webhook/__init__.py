"""Outbound webhook delivery.

Modules:
    publisher.py   `publish(...)` — async POST with timeout + tenacity
                   retry (1 retry, exponential backoff). Logs structured
                   failure on final exhaustion. Never raises into the
                   route handler.
    adapters.py    `to_discord_payload(WebhookPayload) -> dict` and
                   `to_slack_payload(...)` — channel-specific formatting.
"""
