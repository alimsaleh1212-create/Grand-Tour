"""Prompt templates — static system prompts + per-request builder functions.

DESIGN RULES (CLAUDE.md §14, §15)
-----------------------------------
* System prompt = role + format + invariants. Static, never interpolated.
* User prompt = the varying query only. Always sanitised before use.
* Every user-supplied string is wrapped in <user_input>...</user_input> after
  sanitisation so the model can clearly distinguish instructions from data.
* Structured outputs use response_schema (Pydantic) — never free-form parsing.

PUBLIC SURFACE
--------------
    SYSTEM_FEATURE_EXTRACTOR: str
    SYSTEM_FINAL_SYNTHESIS: str

    def build_feature_extractor_prompt(sanitized_question, chunks) -> str
    def build_synthesis_prompt(state) -> str
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.agent.state import AgentState

# ── System prompts (static) ────────────────────────────────────────────────────

SYSTEM_FEATURE_EXTRACTOR = """\
You are a structured data extractor for a travel recommendation system.

Your job: given a list of travel knowledge chunks and a user question, identify \
all distinct destination candidates mentioned in the chunks and extract their \
numeric travel features.

Output a JSON array (one object per destination) with these exact keys:
  destination_name  (string, e.g. "Kyoto")
  region            (string — one of: Europe, Asia, Americas, Africa, Middle East, Oceania)
  avg_temp_c        (float, average annual temperature in °C)
  cost_per_day_usd  (float, typical daily budget in USD)
  safety_index      (float 0–10)
  language_difficulty (float 0–10, 0=easy English, 10=very hard)
  activity_density  (float 0–10)
  nightlife_score   (float 0–10)
  cultural_sites    (float 0–10, count/quality of cultural sites, normalised)
  nature_score      (float 0–10)
  beach_score       (float 0–10)
  family_friendly   (float 0–10)
  infrastructure    (float 0–10)
  luxury_index      (float 0–10)
  latitude          (float, approximate)
  longitude         (float, approximate)
  currency_code     (string, ISO 4217, e.g. "JPY")

Rules:
- Extract values from the text whenever available. Use your world knowledge to \
  fill gaps with reasonable estimates — do not leave fields null.
- Only include destinations that appear in the provided chunks.
- Return ONLY the JSON array, no prose.
"""

SYSTEM_FINAL_SYNTHESIS = """\
You are an expert travel advisor for a Smart Travel Planner application.

Your job: write a warm, personalised travel recommendation that directly answers \
the user's question. Use the structured data provided (retrieved knowledge, \
travel-style classifications, and live conditions) to make the recommendation \
concrete and specific.

Format guidelines:
- Use clear markdown: one H2 heading per recommended destination, bullet points \
  for key facts.
- Lead with the top recommendation. Explain WHY it fits the user's question.
- Include: travel style label, cost estimate, safety note, weather window, and \
  FX rate if available.
- If flights data is available, mention approximate cost.
- Cite the source document (source_url) for each destination in a "Sources" \
  section at the end.
- Keep the answer under 600 words.
- Never hallucinate facts not present in the provided data.
"""

# ── User prompt builders ───────────────────────────────────────────────────────


def build_feature_extractor_prompt(
    sanitized_question: str,
    chunks: list[Any],
) -> str:
    """Build the user turn for the feature-extraction call.

    Args:
        sanitized_question: The cleaned user question.
        chunks: list of SearchHit objects with .text, .destination, .section.

    Returns:
        Formatted user prompt string.
    """
    chunks_text = "\n\n---\n\n".join(
        f"[Destination: {c.destination} | Section: {c.section}]\n{c.text}"
        for c in chunks
    )
    return (
        f"User question:\n<user_input>{sanitized_question}</user_input>\n\n"
        f"Knowledge chunks:\n{chunks_text}"
    )


def build_synthesis_prompt(state: AgentState) -> str:  # type: ignore[type-arg]
    """Build the user turn for the final synthesis call.

    Assembles all accumulated state into a single prompt the strong model
    uses to write the final answer.

    Args:
        state: The completed AgentState after all tool nodes have run.

    Returns:
        Formatted user prompt string.
    """
    question = state.get("sanitized_question", state.get("question", ""))
    hits = state.get("retrieved_hits", [])
    classifications = state.get("classifications", [])
    live_data = state.get("live_data", [])

    # Retrieved chunks summary
    chunks_section = "\n\n".join(
        f"[{h.destination} — {h.section}]\n{h.text}\n(source: {h.source_url or h.source})"
        for h in hits
    )

    # Classification results
    class_lines = [
        f"- {c.destination_name}: {c.predicted_style} "
        f"(confidence {c.confidence:.0%})"
        for c in classifications
    ]
    classifications_section = "\n".join(class_lines) if class_lines else "N/A"

    # Live conditions
    live_lines: list[str] = []
    for dest_idx, lc in enumerate(live_data):
        if lc is None:
            continue
        dest_name = (
            classifications[dest_idx].destination_name
            if dest_idx < len(classifications)
            else f"destination {dest_idx}"
        )
        parts: list[str] = [f"**{dest_name}**"]
        if lc.weather:
            parts.append(
                f"Weather: avg {lc.weather.avg_temp_c:.1f}°C, "
                f"{lc.weather.precipitation_mm:.0f}mm precipitation"
            )
        if lc.fx:
            parts.append(f"FX: 1 {lc.fx.base} = {lc.fx.rate:.4f} {lc.fx.quote}")
        if lc.flights:
            if lc.flights.available and lc.flights.price_total:
                parts.append(
                    f"Flights: ~{lc.flights.currency} "
                    f"{lc.flights.price_total:.0f}"
                )
            else:
                parts.append(f"Flights: {lc.flights.reason or 'unavailable'}")
        live_lines.append(" | ".join(parts))

    live_section = "\n".join(live_lines) if live_lines else "No live data available."

    errors = state.get("errors", [])
    errors_note = (
        f"\nNote: some data was unavailable: {'; '.join(errors)}"
        if errors
        else ""
    )

    return (
        f"User question:\n<user_input>{question}</user_input>\n\n"
        f"## Retrieved knowledge\n{chunks_section}\n\n"
        f"## Travel-style classifications\n{classifications_section}\n\n"
        f"## Live conditions\n{live_section}"
        f"{errors_note}"
    )
