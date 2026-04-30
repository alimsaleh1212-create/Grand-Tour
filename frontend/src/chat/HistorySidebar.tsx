import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/api/client";
import type { RunOut } from "@/api/client";
import Spinner from "@/components/Spinner";

interface Props {
  open: boolean;
  onClose: () => void;
  onSelectRun?: (run: RunOut) => void;
}

export default function HistorySidebar({ open, onClose, onSelectRun }: Props) {
  const [runs, setRuns] = useState<RunOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError(null);
    apiClient
      .get<RunOut[]>("/runs")
      .then((res) => setRuns(res.data))
      .catch(() => setError("Could not load history."))
      .finally(() => setLoading(false));
  }, [open]);

  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          style={{ position: "fixed", inset: 0, zIndex: 49, background: "rgba(30,30,42,0.2)" }}
          onClick={onClose}
        />
      )}

      {/* Drawer */}
      <aside
        style={{
          position: "fixed",
          top: 56,
          left: 0,
          bottom: 0,
          width: 300,
          background: "var(--white)",
          borderRight: "1px solid var(--border)",
          boxShadow: open ? "var(--shadow-lg)" : "none",
          transform: open ? "translateX(0)" : "translateX(-100%)",
          transition: "transform 0.28s cubic-bezier(0.4,0,0.2,1), box-shadow 0.28s",
          zIndex: 50,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
        aria-hidden={!open}
      >
        {/* Header */}
        <div style={{
          padding: "18px 16px 14px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexShrink: 0,
        }}>
          <div style={{ fontFamily: "var(--font-display)", fontSize: 18, color: "var(--teal)" }}>
            Previous Trips
          </div>
          <button
            onClick={onClose}
            aria-label="Close history"
            style={{
              background: "transparent",
              border: "none",
              cursor: "pointer",
              color: "var(--ink-muted)",
              padding: 4,
              fontSize: 16,
            }}
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: "auto", padding: "12px 0" }}>
          {loading && (
            <div style={{ display: "flex", justifyContent: "center", padding: 32 }}>
              <Spinner color="var(--teal)" />
            </div>
          )}
          {error && (
            <div style={{ padding: "12px 16px", color: "var(--error)", fontSize: 13, fontFamily: "var(--font-body)" }}>
              {error}
            </div>
          )}
          {!loading && !error && runs.length === 0 && (
            <div style={{ padding: "24px 16px", textAlign: "center", color: "var(--ink-muted)", fontSize: 13, fontFamily: "var(--font-body)" }}>
              No previous trips yet.<br />Ask your first travel question!
            </div>
          )}
          {runs.map((run) => (
            <RunItem key={run.id} run={run} onSelect={onSelectRun} onClose={onClose} />
          ))}
        </div>
      </aside>
    </>
  );
}

function RunItem({ run, onSelect, onClose }: { run: RunOut; onSelect?: (r: RunOut) => void; onClose: () => void }) {
  const date = new Date(run.started_at).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  const shortQ = run.question.length > 60 ? run.question.slice(0, 60) + "…" : run.question;
  const shortA = run.final_answer
    ? (run.final_answer.length > 80 ? run.final_answer.slice(0, 80) + "…" : run.final_answer)
    : null;

  const handleClick = () => {
    onSelect?.(run);
    onClose();
  };

  return (
    <div
      role="button"
      tabIndex={0}
      style={itemStyle}
      onClick={handleClick}
      onKeyDown={(e) => e.key === "Enter" && handleClick()}
    >
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
        <div style={questionText}>{shortQ}</div>
        <div style={dateText}>{date}</div>
      </div>
      {shortA && <div style={answerPreview}>{shortA}</div>}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 8 }}>
        <span style={costBadge}>${parseFloat(run.cost_usd).toFixed(4)}</span>
        <Link
          to={`/runs/${run.id}`}
          onClick={(e) => e.stopPropagation()}
          style={{ fontSize: 11, color: "var(--teal)", fontWeight: 600, textDecoration: "none", fontFamily: "var(--font-body)" }}
        >
          Details →
        </Link>
      </div>
    </div>
  );
}

const itemStyle: React.CSSProperties = {
  padding: "12px 16px",
  cursor: "pointer",
  borderBottom: "1px solid var(--cream-dark)",
  transition: "background var(--dur-fast)",
  outline: "none",
};

const questionText: React.CSSProperties = {
  fontSize: 13,
  fontFamily: "var(--font-body)",
  fontWeight: 600,
  color: "var(--ink)",
  lineHeight: 1.4,
  flex: 1,
};

const dateText: React.CSSProperties = {
  fontSize: 11,
  fontFamily: "var(--font-body)",
  color: "var(--ink-faint)",
  flexShrink: 0,
};

const answerPreview: React.CSSProperties = {
  fontSize: 12,
  fontFamily: "var(--font-body)",
  color: "var(--ink-muted)",
  lineHeight: 1.45,
  marginTop: 4,
};

const costBadge: React.CSSProperties = {
  fontSize: 11,
  fontFamily: "var(--font-body)",
  fontWeight: 600,
  color: "var(--teal)",
  background: "var(--teal-pale)",
  padding: "2px 8px",
  borderRadius: 999,
};
