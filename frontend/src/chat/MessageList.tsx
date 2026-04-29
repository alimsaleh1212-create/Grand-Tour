/**
 * MessageList — scrollable transcript of user and agent messages.
 *
 * Props:
 *   messages: Message[]  — ordered array of message objects (user | agent)
 *   loading: boolean     — when true renders a "thinking…" skeleton at the end
 *
 * Message shape (Stage 7 will import from @/api/client):
 *   { id: string; role: "user" | "agent"; content: string;
 *     toolsFired?: string[]; runId?: string; timestamp: string }
 *
 * Rendering:
 *   - User messages: right-aligned bubble, primary background.
 *   - Agent messages: left-aligned bubble, surface background.
 *   - Each agent message renders a row of ToolBadge components for every entry
 *     in `toolsFired`.  Clicking a badge navigates to `/runs/:runId`.
 *
 * Auto-scroll:
 *   A `useEffect` on `messages` scrolls the list container to the bottom
 *   whenever a new message arrives, provided the user hasn't manually scrolled
 *   upward (scroll-anchoring check).
 *
 * Implemented in Stage 7.
 */

export interface Message {
  id: string;
  role: "user" | "agent";
  content: string;
  toolsFired?: string[];
  runId?: string;
  timestamp: string;
}

interface Props {
  messages: Message[];
  loading: boolean;
}

export default function MessageList({ messages, loading }: Props) {
  // Implemented in Stage 7
  return (
    <div>
      {messages.length === 0 && <p>No messages yet.</p>}
      {loading && <p>Thinking…</p>}
    </div>
  );
}
