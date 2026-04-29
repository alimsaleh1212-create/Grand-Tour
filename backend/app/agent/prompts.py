"""Prompt templates — separated system vs user, sanitised user content.

Implemented in Stage 5.

Per CLAUDE §18 and §19:
    * System prompt carries role, tone, output format, and invariant
      rules. Static across requests.
    * User prompt carries the varying query only.
    * Every user-supplied string is wrapped in <user_input>...</user_input>
      tags AFTER sanitisation by `agent.security._sanitize_query`.
    * Structured outputs (response_schema / response_mime_type) are used
      for any prompt whose result feeds another stage — never parse
      free-form LLM text with regex.

Constants (planned):
    SYSTEM_PLANNER             # cheap-model: pick which tools to fire
    SYSTEM_ARG_EXTRACTOR       # cheap-model: pull Pydantic args from text
    SYSTEM_FINAL_SYNTHESIS     # strong-model: write the trip plan

Functions (planned):
    def build_planner_user_prompt(sanitized_question: str) -> str: ...
    def build_synthesis_user_prompt(state: AgentState) -> str: ...
"""
