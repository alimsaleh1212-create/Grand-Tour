/**
 * ToolBadge — small pill indicating which agent tool fired for a given message.
 *
 * Props:
 *   toolName: string  — one of "retrieve_destinations" | "classify_style"
 *                         | "live_conditions"
 *   runId: string     — parent run ID; clicking navigates to /runs/:runId
 *
 * Visual:
 *   - Each tool name maps to a distinct colour via a lookup table so the
 *     transcript is scannable at a glance.
 *   - Rendered as an `<a>` tag (links to RunDetail) with `role="status"` label
 *     for screen readers.
 *   - Display name is a human-friendly short form:
 *       "retrieve_destinations" → "📍 Retrieve"
 *       "classify_style"        → "🏷 Classify"
 *       "live_conditions"       → "🌤 Live"
 *
 * Implemented in Stage 7.
 */

interface Props {
  toolName: string;
  runId: string;
}

const LABELS: Record<string, string> = {
  retrieve_destinations: "📍 Retrieve",
  classify_style: "🏷 Classify",
  live_conditions: "🌤 Live",
};

export default function ToolBadge({ toolName, runId }: Props) {
  // Implemented in Stage 7
  return (
    <a href={`/runs/${runId}`} role="status">
      {LABELS[toolName] ?? toolName}
    </a>
  );
}
