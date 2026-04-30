import { Link } from "react-router-dom";

interface Props {
  toolName: string;
  runId?: number | string;
}

const TOOL_CONFIG: Record<string, { label: string; color: string; bg: string; icon: string }> = {
  retrieve_destinations: {
    label: "Destinations",
    icon: "📍",
    color: "var(--teal)",
    bg: "var(--teal-pale)",
  },
  classify_style: {
    label: "Style",
    icon: "🏷",
    color: "#7c5cbf",
    bg: "#f0ebfb",
  },
  live_conditions: {
    label: "Live Data",
    icon: "🌤",
    color: "#d4860a",
    bg: "#fef4e0",
  },
};

export default function ToolBadge({ toolName, runId }: Props) {
  const cfg = TOOL_CONFIG[toolName] ?? {
    label: toolName,
    icon: "⚙",
    color: "var(--ink-muted)",
    bg: "var(--cream-dark)",
  };

  const content = (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "3px 10px",
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 600,
        fontFamily: "var(--font-body)",
        letterSpacing: "0.04em",
        color: cfg.color,
        background: cfg.bg,
        border: `1px solid ${cfg.color}30`,
        textDecoration: "none",
        cursor: runId ? "pointer" : "default",
        transition: "opacity var(--dur-fast)",
      }}
    >
      <span>{cfg.icon}</span>
      {cfg.label}
    </span>
  );

  if (runId) {
    return (
      <Link to={`/runs/${runId}`} style={{ textDecoration: "none" }} role="status">
        {content}
      </Link>
    );
  }
  return <span role="status">{content}</span>;
}
