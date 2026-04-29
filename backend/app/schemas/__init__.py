"""Pydantic request/response schemas — the HTTP boundary fence.

Per the brief: "Every function in your codebase has type hints. Every
external boundary — HTTP request bodies, tool inputs, LLM structured
outputs, webhook payloads — is a Pydantic model. Pydantic is your fence:
data is validated when it crosses in, and after that you trust your types."

Modules:
    auth.py     SignupRequest, LoginRequest, AccessTokenResponse, UserOut
    chat.py     ChatRequest (question + optional webhook_url), ChatResponse
                (run_id, answer, tools_fired)
    agent.py    AgentRunOut, ToolCallOut — projections used by /runs
    webhook.py  WebhookPayload — outbound shape sent to Discord/Slack
"""
