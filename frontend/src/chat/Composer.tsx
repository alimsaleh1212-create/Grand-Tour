import { useState, useRef, useEffect, type KeyboardEvent } from "react";
import Spinner from "@/components/Spinner";

interface Props {
  onSend: (question: string, webhookUrl?: string) => void;
  disabled: boolean;
}

export default function Composer({ onSend, disabled }: Props) {
  const [text, setText] = useState("");
  const [webhookUrl, setWebhookUrl] = useState(
    () => sessionStorage.getItem("stp_webhook_url") ?? ""
  );
  const [showWebhook, setShowWebhook] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea up to 5 lines
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    const lineH = parseInt(getComputedStyle(ta).lineHeight) || 22;
    ta.style.height = Math.min(ta.scrollHeight, lineH * 5 + 24) + "px";
  }, [text]);

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function submit() {
    const q = text.trim();
    if (!q || disabled) return;
    onSend(q, webhookUrl || undefined);
    setText("");
  }

  function handleWebhookChange(v: string) {
    setWebhookUrl(v);
    sessionStorage.setItem("stp_webhook_url", v);
  }

  return (
    <div style={wrapper}>
      {/* Webhook disclosure */}
      <div style={{ marginBottom: showWebhook ? 8 : 0 }}>
        <button
          type="button"
          onClick={() => setShowWebhook((p) => !p)}
          style={webhookToggle}
        >
          <span style={{ transform: showWebhook ? "rotate(90deg)" : "none", display: "inline-block", transition: "transform 0.2s" }}>▸</span>
          Webhook URL (optional)
        </button>
        {showWebhook && (
          <input
            type="url"
            className="input"
            placeholder="https://discord.com/api/webhooks/…"
            value={webhookUrl}
            onChange={(e) => handleWebhookChange(e.target.value)}
            style={{ marginTop: 6, fontSize: 13 }}
          />
        )}
      </div>

      {/* Input row */}
      <div style={inputRow}>
        <textarea
          ref={textareaRef}
          aria-label="Ask about a destination"
          placeholder="Where would you like to travel? Ask me anything…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
          style={textareaStyle}
        />
        <button
          type="button"
          aria-label="Send message"
          onClick={submit}
          disabled={disabled || !text.trim()}
          style={{
            ...sendBtn,
            background: disabled || !text.trim() ? "var(--ink-faint)" : "var(--teal)",
          }}
        >
          {disabled ? (
            <Spinner size="sm" color="white" label="Thinking…" />
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          )}
        </button>
      </div>

      <div style={{ fontSize: 11, color: "var(--ink-faint)", fontFamily: "var(--font-body)", marginTop: 6, textAlign: "center" }}>
        Enter to send · Shift+Enter for new line
      </div>
    </div>
  );
}

const wrapper: React.CSSProperties = {
  padding: "12px 16px 16px",
  borderTop: "1px solid var(--border)",
  background: "var(--white)",
  flexShrink: 0,
};

const webhookToggle: React.CSSProperties = {
  background: "none",
  border: "none",
  cursor: "pointer",
  fontSize: 12,
  color: "var(--ink-muted)",
  fontFamily: "var(--font-body)",
  fontWeight: 600,
  letterSpacing: "0.04em",
  display: "flex",
  alignItems: "center",
  gap: 5,
  padding: "2px 0",
};

const inputRow: React.CSSProperties = {
  display: "flex",
  gap: 10,
  alignItems: "flex-end",
};

const textareaStyle: React.CSSProperties = {
  flex: 1,
  resize: "none",
  padding: "10px 14px",
  borderRadius: "var(--r-lg)",
  border: "1.5px solid var(--border)",
  fontFamily: "var(--font-body)",
  fontSize: 14,
  color: "var(--ink)",
  background: "var(--cream)",
  outline: "none",
  lineHeight: 1.55,
  transition: "border-color var(--dur-fast), box-shadow var(--dur-fast)",
  overflowY: "hidden",
};

const sendBtn: React.CSSProperties = {
  width: 44,
  height: 44,
  borderRadius: "var(--r-lg)",
  border: "none",
  color: "white",
  cursor: "pointer",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  flexShrink: 0,
  transition: "background var(--dur-fast)",
};
