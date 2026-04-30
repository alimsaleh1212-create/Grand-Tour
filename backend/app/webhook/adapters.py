"""Channel-specific payload adapters — Discord and Slack.

Each function converts (question, answer, run_id) into the JSON payload
the target service expects.

PUBLIC SURFACE
--------------
    def discord_payload(question, answer, run_id) -> dict
    def slack_payload(question, answer, run_id) -> dict
    def build_payload(url, question, answer, run_id) -> dict
"""

from __future__ import annotations


def discord_payload(
    question: str,
    answer: str,
    run_id: int,
) -> dict[str, object]:
    """Build a Discord webhook payload (embeds format)."""
    truncated_answer = answer[:1800] + "…" if len(answer) > 1800 else answer
    return {
        "embeds": [
            {
                "title": "✈️ Smart Travel Planner — Run Complete",
                "description": f"**Q:** {question[:200]}\n\n**A:** {truncated_answer}",
                "color": 0x1A6B7A,
                "footer": {"text": f"Run #{run_id}"},
            }
        ]
    }


def slack_payload(
    question: str,
    answer: str,
    run_id: int,
) -> dict[str, object]:
    """Build a Slack webhook payload (blocks format)."""
    truncated_answer = answer[:2900] + "…" if len(answer) > 2900 else answer
    return {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "✈️ Smart Travel Planner — Run Complete",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Q:* {question[:200]}\n\n*A:* {truncated_answer}",
                },
            },
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"Run #{run_id}"}],
            },
        ]
    }


def build_payload(
    url: str,
    question: str,
    answer: str,
    run_id: int,
) -> dict[str, object]:
    """Choose the right adapter based on the URL domain."""
    if "discord.com" in url or "discordapp.com" in url:
        return discord_payload(question, answer, run_id)
    if "hooks.slack.com" in url:
        return slack_payload(question, answer, run_id)
    # Generic JSON fallback for custom endpoints
    return {
        "run_id": run_id,
        "question": question,
        "answer": answer,
    }
