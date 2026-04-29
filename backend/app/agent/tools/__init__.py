"""Agent tools — `BaseTool` ABC plus three concrete subclasses.

Modules:
    base.py                   BaseTool ABC; safe_run() wrapper that
                              validates args and converts exceptions into
                              structured ToolResult objects (never raises
                              into the agent loop).
    retrieve_destinations.py  RAG search via embedder + vector store.
    classify_style.py         Predict travel style from feature dict using
                              the lifespan-loaded classifier.
    live_conditions.py        Weather (Open-Meteo, no key) + FX
                              (exchangerate.host, no key) + flights
                              (Amadeus, key-gated, graceful degradation).

The agent uses the tool name (`tool.name` class attribute) as the
allowlist key. To add a tool: subclass BaseTool, register it in the
agent's tool registry. Nothing else changes.
"""
