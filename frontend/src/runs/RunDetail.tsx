/**
 * RunDetail — full tool-call timeline for a single agent run.
 *
 * Route: /runs/:id  (id = AgentRun.id UUID)
 *
 * Data fetching:
 *   Calls `GET /runs/:id` on mount.  The response includes the run metadata
 *   (question, final_answer, cost_usd, started_at, finished_at) and a
 *   `tool_calls` array with per-tool details.
 *
 * Layout:
 *   ┌──────────────────────────────────────┐
 *   │ ← Back to chat   Run #<short-id>    │
 *   ├──────────────────────────────────────┤
 *   │ Question: "…"                        │
 *   │ Answer:   "…"                        │
 *   │ Cost: $0.0042  |  Duration: 4.2 s    │
 *   ├──────────────────────────────────────┤
 *   │ Tool timeline (vertical)             │
 *   │   [retrieve_destinations] 312 ms     │
 *   │     args: { query_text: "…", … }     │
 *   │     result: { chunks: […] }          │
 *   │   [classify_style]       8 ms        │
 *   │     …                                │
 *   │   [live_conditions]      1240 ms     │
 *   │     …                                │
 *   └──────────────────────────────────────┘
 *
 * Error states:
 *   - 404: "Run not found (or belongs to another user)" — no run ID leak.
 *   - Network error: generic banner with a retry button.
 *
 * Implemented in Stage 7.
 */

export default function RunDetail() {
  // Implemented in Stage 7
  return (
    <div>
      <h1>Run Detail</h1>
      <p>Implemented in Stage 7.</p>
    </div>
  );
}
