import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { apiClient } from "@/api/client";
import type { RunDetailOut, ToolCallOut } from "@/api/client";
import NavBar from "@/components/NavBar";
import Spinner from "@/components/Spinner";
import ToolBadge from "@/components/ToolBadge";

const TOOL_ICON: Record<string, string> = {
  retrieve_destinations: "📍",
  classify_style: "🏷",
  live_conditions: "🌤",
};

export default function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<RunDetailOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    apiClient
      .get<RunDetailOut>(`/runs/${id}`)
      .then((res) => setRun(res.data))
      .catch((err) => {
        const status = (err as { response?: { status?: number } }).response?.status;
        setError(status === 404 ? "Run not found." : "Could not load run details.");
      })
      .finally(() => setLoading(false));
  }, [id]);

  const durationSec = run?.finished_at && run?.started_at
    ? ((new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000).toFixed(1)
    : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh", background: "var(--cream)" }}>
      <NavBar />

      <div style={{ maxWidth: 840, margin: "0 auto", width: "100%", padding: "28px 20px" }}>
        {/* Back */}
        <Link
          to="/chat"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            color: "var(--teal)",
            fontFamily: "var(--font-body)",
            fontSize: 13,
            fontWeight: 600,
            textDecoration: "none",
            marginBottom: 24,
          }}
        >
          ← Back to Chat
        </Link>

        {loading && (
          <div style={{ display: "flex", justifyContent: "center", padding: 60 }}>
            <Spinner size="lg" color="var(--teal)" />
          </div>
        )}

        {error && (
          <div style={{
            padding: "16px 20px",
            background: "#fdf0ef",
            border: "1px solid #f5c2bb",
            borderRadius: "var(--r-md)",
            color: "var(--error)",
            fontFamily: "var(--font-body)",
            fontSize: 14,
          }}>
            {error}
          </div>
        )}

        {run && (
          <div style={{ animation: "fadeSlideUp 0.4s cubic-bezier(0.4,0,0.2,1) both" }}>
            {/* Run header card */}
            <div style={headerCard}>
              <div style={{ marginBottom: 16 }}>
                <div style={runIdLabel}>
                  Run #{run.id}
                </div>
                <h1 style={questionHeading}>{run.question}</h1>
              </div>

              {/* Meta strip */}
              <div style={metaStrip}>
                <MetaChip label="Status" value={run.status} icon="⚡" />
                {durationSec && <MetaChip label="Duration" value={`${durationSec}s`} icon="⏱" />}
                <MetaChip label="Cost" value={`$${parseFloat(run.cost_usd).toFixed(4)}`} icon="💰" />
                <MetaChip label="Tokens (fast)" value={String(run.total_tokens_cheap)} icon="🔤" />
                <MetaChip label="Tokens (strong)" value={String(run.total_tokens_strong)} icon="🔤" />
              </div>
            </div>

            {/* Tool timeline */}
            {run.tool_calls.length > 0 && (
              <div style={section}>
                <h2 style={sectionTitle}>Tool Timeline</h2>
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  {run.tool_calls.map((tc) => (
                    <ToolCallCard key={tc.id} tc={tc} />
                  ))}
                </div>
              </div>
            )}

            {/* Final answer */}
            {run.final_answer && (
              <div style={section}>
                <h2 style={sectionTitle}>Final Answer</h2>
                <div style={answerCard}>
                  {run.final_answer.split("\n").map((line, i) => {
                    if (!line.trim()) return <br key={i} />;
                    if (line.startsWith("# ")) return <h2 key={i} style={{ fontFamily: "var(--font-display)", fontSize: 22, color: "var(--teal)", margin: "14px 0 6px" }}>{line.slice(2)}</h2>;
                    if (line.startsWith("## ")) return <h3 key={i} style={{ fontFamily: "var(--font-display)", fontSize: 18, margin: "10px 0 4px" }}>{line.slice(3)}</h3>;
                    if (line.startsWith("- ") || line.startsWith("* ")) {
                      return <div key={i} style={{ fontSize: 14, fontFamily: "var(--font-body)", lineHeight: 1.6, paddingLeft: 4, marginBottom: 3 }}><span style={{ color: "var(--gold)", marginRight: 6 }}>•</span>{line.slice(2)}</div>;
                    }
                    return <p key={i} style={{ fontSize: 14, fontFamily: "var(--font-body)", lineHeight: 1.7, marginBottom: 5 }}>{line}</p>;
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function MetaChip({ label, value, icon }: { label: string; value: string; icon: string }) {
  return (
    <div style={metaChip}>
      <span style={{ fontSize: 14 }}>{icon}</span>
      <div>
        <div style={{ fontSize: 10, fontWeight: 700, fontFamily: "var(--font-body)", letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--ink-faint)" }}>{label}</div>
        <div style={{ fontSize: 13, fontWeight: 600, fontFamily: "var(--font-body)", color: "var(--ink)" }}>{value}</div>
      </div>
    </div>
  );
}

function ToolCallCard({ tc }: { tc: ToolCallOut }) {
  const [expanded, setExpanded] = useState(false);
  const icon = TOOL_ICON[tc.tool_name] ?? "⚙";

  return (
    <div style={toolCard}>
      <div
        style={toolCardHeader}
        onClick={() => setExpanded((p) => !p)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && setExpanded((p) => !p)}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 18 }}>{icon}</span>
          <ToolBadge toolName={tc.tool_name} />
          {tc.error && (
            <span style={{ fontSize: 11, fontWeight: 700, color: "var(--error)", fontFamily: "var(--font-body)" }}>
              FAILED
            </span>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {tc.latency_ms > 0 && (
            <span style={{ fontSize: 12, color: "var(--ink-muted)", fontFamily: "var(--font-body)" }}>
              {tc.latency_ms}ms
            </span>
          )}
          <span style={{ color: "var(--ink-faint)", fontSize: 14, transform: expanded ? "rotate(90deg)" : "none", display: "inline-block", transition: "transform 0.2s" }}>▸</span>
        </div>
      </div>

      {expanded && (
        <div style={{ padding: "14px 16px", borderTop: "1px solid var(--cream-dark)" }}>
          <JsonBlock label="Arguments" data={tc.args_json} />
          <JsonBlock label="Result" data={tc.result_json} />
          {tc.error && (
            <div style={{ marginTop: 10, padding: "8px 12px", background: "#fdf0ef", borderRadius: "var(--r-sm)", color: "var(--error)", fontSize: 12, fontFamily: "monospace" }}>
              {tc.error}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function JsonBlock({ label, data }: { label: string; data: unknown }) {
  if (!data || (typeof data === "object" && Object.keys(data as object).length === 0)) return null;
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 10, fontWeight: 700, fontFamily: "var(--font-body)", letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--ink-muted)", marginBottom: 4 }}>
        {label}
      </div>
      <pre style={{
        fontSize: 12,
        fontFamily: "monospace",
        color: "var(--ink)",
        background: "var(--cream)",
        border: "1px solid var(--border)",
        borderRadius: "var(--r-sm)",
        padding: "10px 12px",
        overflowX: "auto",
        lineHeight: 1.5,
        maxHeight: 200,
        overflowY: "auto",
      }}>
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────

const headerCard: React.CSSProperties = {
  background: "var(--white)",
  border: "1px solid var(--border)",
  borderRadius: "var(--r-xl)",
  padding: "24px 28px",
  marginBottom: 24,
  boxShadow: "var(--shadow-sm)",
};

const runIdLabel: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 700,
  fontFamily: "var(--font-body)",
  letterSpacing: "0.1em",
  textTransform: "uppercase",
  color: "var(--teal)",
  marginBottom: 8,
};

const questionHeading: React.CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: 26,
  fontWeight: 500,
  color: "var(--ink)",
  letterSpacing: "0.02em",
};

const metaStrip: React.CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 10,
};

const metaChip: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  padding: "8px 14px",
  background: "var(--cream)",
  border: "1px solid var(--border)",
  borderRadius: "var(--r-md)",
};

const section: React.CSSProperties = {
  marginBottom: 28,
};

const sectionTitle: React.CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: 20,
  fontWeight: 500,
  color: "var(--ink)",
  marginBottom: 14,
};

const toolCard: React.CSSProperties = {
  background: "var(--white)",
  border: "1px solid var(--border)",
  borderRadius: "var(--r-md)",
  boxShadow: "var(--shadow-xs)",
  overflow: "hidden",
};

const toolCardHeader: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "12px 16px",
  cursor: "pointer",
  outline: "none",
};

const answerCard: React.CSSProperties = {
  background: "var(--white)",
  border: "1px solid var(--border)",
  borderRadius: "var(--r-lg)",
  padding: "20px 24px",
  boxShadow: "var(--shadow-xs)",
};
