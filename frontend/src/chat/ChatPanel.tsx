import { useState, useRef, useCallback } from "react";
import NavBar from "@/components/NavBar";
import Composer from "./Composer";
import HistorySidebar from "./HistorySidebar";
import BookingModal from "./BookingModal";
import { RetrieveCards, ClassifyCards, LiveCards, TravelPlanAnswer } from "./TravelPlanCards";
import { streamChat } from "@/api/client";
import type { SseChunk, SseClassification, SseLiveConditions, BookingOut } from "@/api/client";
import ToolBadge from "@/components/ToolBadge";
import Spinner from "@/components/Spinner";

// ── Message model ──────────────────────────────────────────────────────────

interface UserMessage {
  kind: "user";
  id: string;
  text: string;
}

interface AgentMessage {
  kind: "agent";
  id: string;
  runId?: number;
  chunks?: SseChunk[];
  classifications?: SseClassification[];
  liveData?: SseLiveConditions[];
  answer?: string;
  streaming: boolean;
  error?: string;
  costUsd?: number;
  toolsFired: string[];
}

type Message = UserMessage | AgentMessage;

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

// ── Booking context ────────────────────────────────────────────────────────

interface BookingTarget {
  flight: Record<string, unknown>;
  runId?: number;
}

// ── ChatPanel ──────────────────────────────────────────────────────────────

export default function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [bookingTarget, setBookingTarget] = useState<BookingTarget | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  function scrollToBottom() {
    setTimeout(() => {
      if (listRef.current) {
        listRef.current.scrollTop = listRef.current.scrollHeight;
      }
    }, 30);
  }

  function updateAgent(id: string, patch: Partial<AgentMessage>) {
    setMessages((prev) =>
      prev.map((m) => (m.id === id && m.kind === "agent" ? { ...m, ...patch } : m))
    );
    scrollToBottom();
  }

  const handleSend = useCallback(async (question: string, webhookUrl?: string) => {
    if (streaming) return;

    // Abort any previous stream
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const userMsg: UserMessage = { kind: "user", id: uid(), text: question };
    const agentId = uid();
    const agentMsg: AgentMessage = {
      kind: "agent",
      id: agentId,
      streaming: true,
      toolsFired: [],
    };

    setMessages((prev) => [...prev, userMsg, agentMsg]);
    setStreaming(true);
    scrollToBottom();

    try {
      const gen = streamChat({ question, webhook_url: webhookUrl }, controller.signal);
      for await (const event of gen) {
        if (event.type === "retrieve_result") {
          updateAgent(agentId, {
            chunks: event.chunks,
            toolsFired: ["retrieve_destinations"],
          });
        } else if (event.type === "classify_result") {
          updateAgent(agentId, {
            classifications: event.classifications,
            toolsFired: ["retrieve_destinations", "classify_style"],
          });
        } else if (event.type === "live_result") {
          updateAgent(agentId, {
            liveData: event.live_data,
            toolsFired: ["retrieve_destinations", "classify_style", "live_conditions"],
          });
        } else if (event.type === "answer") {
          updateAgent(agentId, { answer: event.text });
        } else if (event.type === "done") {
          updateAgent(agentId, { streaming: false, runId: event.run_id, costUsd: event.cost_usd });
        } else if (event.type === "booking_request") {
          setBookingTarget({ flight: event.flight, runId: undefined });
        } else if (event.type === "error") {
          updateAgent(agentId, { streaming: false, error: event.detail });
        }
      }
    } catch (err: unknown) {
      const isAbort = (err as Error)?.name === "AbortError";
      if (!isAbort) {
        updateAgent(agentId, {
          streaming: false,
          error: "Connection error. Please try again.",
        });
      }
    } finally {
      setStreaming(false);
      updateAgent(agentId, { streaming: false });
    }
  }, [streaming]);

  const handleBookFlight = useCallback(
    (flight: Record<string, unknown>, runId?: number) => {
      setBookingTarget({ flight, runId });
    },
    []
  );

  const handleBooked = useCallback((booking: BookingOut) => {
    // Show a confirmation message in the chat
    const confirmMsg: AgentMessage = {
      kind: "agent",
      id: uid(),
      streaming: false,
      toolsFired: [],
      answer: `✅ **Flight booked!** Your booking reference is \`${booking.booking_ref}\`. Check your email at ${booking.passenger_name} for the confirmation details. This is a demo booking — no real ticket was issued.`,
    };
    setMessages((prev) => [...prev, confirmMsg]);
    scrollToBottom();
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "var(--cream)" }}>
      <NavBar onToggleSidebar={() => setSidebarOpen((p) => !p)} sidebarOpen={sidebarOpen} />

      <HistorySidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      {/* Message list */}
      <div ref={listRef} style={listStyle}>
        {messages.length === 0 && <WelcomeScreen />}
        {messages.map((msg) =>
          msg.kind === "user" ? (
            <UserBubble key={msg.id} text={msg.text} />
          ) : (
            <AgentBubble
              key={msg.id}
              msg={msg}
              onBookFlight={(f) => handleBookFlight(f, msg.runId)}
            />
          )
        )}
      </div>

      <Composer onSend={handleSend} disabled={streaming} />

      {bookingTarget && (
        <BookingModal
          flight={bookingTarget.flight}
          runId={bookingTarget.runId}
          onClose={() => setBookingTarget(null)}
          onBooked={(b) => {
            setBookingTarget(null);
            handleBooked(b);
          }}
        />
      )}
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────

function WelcomeScreen() {
  return (
    <div style={welcomeWrap}>
      <div style={welcomeIcon}>✈</div>
      <h1 style={welcomeTitle}>Grand Tour</h1>
      <p style={welcomeSub}>
        Your AI-powered travel planner. Ask me about destinations, travel styles,
        costs, weather, and I'll craft a personalised trip plan for you.
      </p>
      <div style={welcomeSuggestions}>
        {[
          "Plan a week in Kyoto for a culture lover",
          "Budget adventure trip in Southeast Asia",
          "Luxury beach holiday in Maldives",
          "Family-friendly destinations in Europe",
        ].map((s) => (
          <div key={s} style={suggestionChip}>{s}</div>
        ))}
      </div>
    </div>
  );
}

function UserBubble({ text }: { text: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 16, padding: "0 16px" }}>
      <div style={userBubble}>{text}</div>
    </div>
  );
}

function AgentBubble({ msg, onBookFlight }: {
  msg: AgentMessage;
  onBookFlight: (f: Record<string, unknown>) => void;
}) {
  return (
    <div style={{ padding: "0 16px", marginBottom: 20, animation: "fadeSlideUp 0.35s cubic-bezier(0.4,0,0.2,1) both" }}>
      {/* Tool badges row */}
      {msg.toolsFired.length > 0 && (
        <div style={{ display: "flex", gap: 6, marginBottom: 10, flexWrap: "wrap" }}>
          {msg.toolsFired.map((t) => (
            <ToolBadge key={t} toolName={t} runId={msg.runId} />
          ))}
        </div>
      )}

      {/* Streaming indicator */}
      {msg.streaming && !msg.chunks && !msg.answer && (
        <div style={thinkingIndicator}>
          <Spinner size="sm" color="var(--teal)" />
          <span style={{ marginLeft: 8, color: "var(--ink-muted)", fontSize: 13, fontFamily: "var(--font-body)" }}>
            Searching destinations…
          </span>
        </div>
      )}

      {/* Progressive results */}
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {msg.chunks && msg.chunks.length > 0 && (
          <RetrieveCards chunks={msg.chunks} />
        )}

        {msg.classifications && msg.classifications.length > 0 && (
          <ClassifyCards classifications={msg.classifications} />
        )}

        {msg.liveData && msg.liveData.length > 0 && (
          <LiveCards
            liveData={msg.liveData}
            onBookFlight={(f) => onBookFlight(f as Record<string, unknown>)}
          />
        )}

        {msg.streaming && msg.chunks && !msg.answer && (
          <div style={thinkingIndicator}>
            <Spinner size="sm" color="var(--teal)" />
            <span style={{ marginLeft: 8, color: "var(--ink-muted)", fontSize: 13, fontFamily: "var(--font-body)" }}>
              Synthesising your travel plan…
            </span>
          </div>
        )}

        {msg.answer && (
          <TravelPlanAnswer text={msg.answer} streaming={msg.streaming} />
        )}

        {msg.error && (
          <div style={errorBox} role="alert">
            <span style={{ fontSize: 16 }}>⚠️</span>
            <span style={{ fontSize: 13, fontFamily: "var(--font-body)" }}>{msg.error}</span>
          </div>
        )}

        {/* Cost + run link */}
        {!msg.streaming && msg.costUsd != null && msg.runId != null && (
          <div style={metaRow}>
            <span style={costLabel}>Cost: ${msg.costUsd.toFixed(4)}</span>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────

const listStyle: React.CSSProperties = {
  flex: 1,
  overflowY: "auto",
  padding: "24px 0 8px",
};

const welcomeWrap: React.CSSProperties = {
  maxWidth: 560,
  margin: "60px auto 0",
  textAlign: "center",
  padding: "0 24px",
  animation: "fadeSlideUp 0.5s cubic-bezier(0.4,0,0.2,1) both",
};

const welcomeIcon: React.CSSProperties = {
  width: 72,
  height: 72,
  borderRadius: "50%",
  background: "var(--teal)",
  color: "white",
  fontSize: 32,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  margin: "0 auto 20px",
  boxShadow: "0 8px 28px rgba(26,107,122,0.28)",
};

const welcomeTitle: React.CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: 42,
  fontWeight: 400,
  color: "var(--teal)",
  letterSpacing: "0.06em",
  marginBottom: 12,
};

const welcomeSub: React.CSSProperties = {
  fontFamily: "var(--font-body)",
  fontSize: 15,
  color: "var(--ink-muted)",
  lineHeight: 1.65,
  marginBottom: 28,
};

const welcomeSuggestions: React.CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 8,
  justifyContent: "center",
};

const suggestionChip: React.CSSProperties = {
  padding: "8px 16px",
  background: "var(--white)",
  border: "1px solid var(--border)",
  borderRadius: 999,
  fontSize: 13,
  fontFamily: "var(--font-body)",
  color: "var(--ink-muted)",
  cursor: "default",
  boxShadow: "var(--shadow-xs)",
};

const userBubble: React.CSSProperties = {
  background: "var(--teal)",
  color: "white",
  padding: "10px 16px",
  borderRadius: "18px 18px 4px 18px",
  maxWidth: "75%",
  fontSize: 14,
  fontFamily: "var(--font-body)",
  lineHeight: 1.55,
  boxShadow: "var(--shadow-sm)",
};

const thinkingIndicator: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  padding: "12px 16px",
  background: "var(--white)",
  border: "1px solid var(--border)",
  borderRadius: "var(--r-lg)",
  boxShadow: "var(--shadow-xs)",
};

const errorBox: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 10,
  padding: "12px 16px",
  background: "#fdf0ef",
  border: "1px solid #f5c2bb",
  borderRadius: "var(--r-md)",
  color: "var(--error)",
};

const metaRow: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 12,
  paddingLeft: 4,
};

const costLabel: React.CSSProperties = {
  fontSize: 11,
  fontFamily: "var(--font-body)",
  fontWeight: 600,
  color: "var(--ink-faint)",
};
