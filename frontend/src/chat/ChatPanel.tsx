/**
 * ChatPanel — top-level page for the conversational travel-planning interface.
 *
 * Layout (three-column on desktop, stacked on mobile):
 *   ┌────────────────────────────────┐
 *   │  NavBar (email + sign out)     │
 *   ├────────────────────────────────┤
 *   │  MessageList                   │  ← scrollable transcript
 *   │  (user bubbles + agent replies │
 *   │   with ToolBadge components)   │
 *   ├────────────────────────────────┤
 *   │  Composer (textarea + send)    │
 *   └────────────────────────────────┘
 *
 * State:
 *   - `messages: Message[]` — local accumulator; seeded from GET /runs on mount
 *     so history survives page refresh.
 *   - `loading: boolean` — true while the POST /chat request is in-flight.
 *
 * On send:
 *   1. Appends a user bubble immediately (optimistic).
 *   2. Calls `POST /chat` via apiClient.
 *   3. Appends the agent reply with `tools_fired` badges when the response
 *      arrives.
 *   4. Navigating to `/runs/:run_id` shows the full tool-call timeline.
 *
 * Webhook URL:
 *   An optional disclosure (`<details>`) lets the user paste a Discord webhook
 *   URL before sending.  The value is stored in a ref (never in React state) to
 *   avoid re-renders.
 *
 * Implemented in Stage 7.
 */

export default function ChatPanel() {
  // Implemented in Stage 7
  return (
    <div>
      <h1>Chat</h1>
      <p>Implemented in Stage 7.</p>
    </div>
  );
}
