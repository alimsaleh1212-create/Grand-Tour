/**
 * Composer — the message input area at the bottom of ChatPanel.
 *
 * Props:
 *   onSend: (question: string, webhookUrl?: string) => void
 *   disabled: boolean  — true while a request is in-flight
 *
 * UX:
 *   - Textarea grows up to 5 lines, then scrolls.
 *   - Enter submits; Shift+Enter inserts a newline (standard chat convention).
 *   - Submitting an empty or whitespace-only string is a no-op.
 *   - A collapsible `<details>` below the textarea reveals an optional Discord
 *     Webhook URL field.  Remembered across reloads via sessionStorage.
 *
 * Accessibility:
 *   - `aria-label` on the textarea ("Ask about a destination").
 *   - Send button has `aria-label="Send message"`.
 *   - Both the textarea and button are `disabled` when `disabled` prop is true,
 *     preventing double-submit.
 *
 * Implemented in Stage 7.
 */

interface Props {
  onSend: (question: string, webhookUrl?: string) => void;
  disabled: boolean;
}

export default function Composer({ onSend, disabled }: Props) {
  // Implemented in Stage 7
  return (
    <form onSubmit={(e) => { e.preventDefault(); onSend(""); }}>
      <textarea aria-label="Ask about a destination" disabled={disabled} />
      <button type="submit" aria-label="Send message" disabled={disabled}>
        Send
      </button>
    </form>
  );
}
