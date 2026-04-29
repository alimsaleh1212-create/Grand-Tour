"""Agent — LangGraph state machine + 3 tools + two-model pipeline.

The agent answers travel questions by composing three tools and two LLMs:

    cheap LLM (Gemini Flash)   — query rewriting, tool routing, arg
                                 extraction from RAG output, summarisation
                                 of intermediate results.
    strong LLM (Gemini Pro)    — final synthesis only.

    Tool 1  retrieve_destinations  — RAG over pgvector store.
    Tool 2  classify_style          — call the trained joblib classifier.
    Tool 3  live_conditions         — weather + FX + (optional) flights.

Modules:
    state.py        AgentState TypedDict (graph carries this).
    prompts.py      System and user prompts; user input always wrapped
                    in <user_input>...</user_input> per CLAUDE §19.
    llm_clients.py  Cached cheap and strong Gemini clients.
    security.py     _sanitize_query, _sanitize_feature_string,
                    suspicious-pattern logger.
    graph.py        The compiled LangGraph state machine.
    tools/          BaseTool ABC + the three concrete tools.
"""
