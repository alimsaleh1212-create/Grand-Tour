"""Channel-specific payload adapters.

Implemented in Stage 8.

Public surface (planned):
    def to_discord_payload(payload: WebhookPayload) -> dict: ...
        # Builds a Discord embed:
        #   { "embeds": [{ "title": ..., "description": ..., "fields": [...] }] }
        # Truncates description to ≤ 2000 chars (Discord limit).

    def to_slack_payload(payload: WebhookPayload) -> dict: ...
        # Builds a Slack Block Kit message:
        #   { "blocks": [{ "type": "header", ... }, { "type": "section", ... }] }

The webhook_service decides which adapter to call based on the request's
configured target type (default: discord).
"""
