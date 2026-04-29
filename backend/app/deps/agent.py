"""Agent executor dependency.

Implemented in Stage 5.

Public surface (planned):
    async def get_agent(request: Request) -> CompiledGraph:
        return request.app.state.agent

The compiled LangGraph (with the cheap+strong LLM clients, vector-store
handle, ML classifier handle, and live-conditions HTTP client all bound)
is constructed once in lifespan startup and stored on `app.state.agent`.
Tests override this with a fake graph that exercises tool wiring without
calling Gemini.
"""
