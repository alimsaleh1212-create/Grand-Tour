import { Link } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";

interface Props {
  onToggleSidebar?: () => void;
  sidebarOpen?: boolean;
}

export default function NavBar({ onToggleSidebar, sidebarOpen }: Props) {
  const { user, logout } = useAuth();

  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 100,
        background: "var(--teal)",
        borderBottom: "1px solid rgba(255,255,255,0.12)",
        boxShadow: "0 2px 12px rgba(26,107,122,0.25)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "0 20px",
          height: 56,
          maxWidth: 1400,
          margin: "0 auto",
        }}
      >
        {/* Sidebar toggle */}
        {onToggleSidebar && (
          <button
            onClick={onToggleSidebar}
            aria-label={sidebarOpen ? "Close history" : "Open history"}
            style={{
              background: "rgba(255,255,255,0.12)",
              border: "1px solid rgba(255,255,255,0.2)",
              borderRadius: "var(--r-sm)",
              color: "white",
              cursor: "pointer",
              padding: "6px 8px",
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 13,
              fontFamily: "var(--font-body)",
              fontWeight: 600,
              letterSpacing: "0.04em",
              transition: "background var(--dur-fast)",
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
            History
          </button>
        )}

        {/* Brand */}
        <Link
          to="/chat"
          style={{
            fontFamily: "var(--font-display)",
            fontSize: 22,
            fontWeight: 500,
            color: "white",
            textDecoration: "none",
            letterSpacing: "0.04em",
            display: "flex",
            alignItems: "center",
            gap: 8,
            flexShrink: 0,
          }}
        >
          <span style={{ fontSize: 20 }}>✈</span>
          Grand Tour
        </Link>

        <span style={{ flex: 1 }} />

        {/* User */}
        {user && (
          <span
            style={{
              color: "rgba(255,255,255,0.75)",
              fontSize: 13,
              fontFamily: "var(--font-body)",
              maxWidth: 200,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {user.email}
          </span>
        )}

        <button
          onClick={logout}
          style={{
            background: "rgba(255,255,255,0.12)",
            border: "1px solid rgba(255,255,255,0.2)",
            borderRadius: "var(--r-sm)",
            color: "white",
            cursor: "pointer",
            padding: "6px 14px",
            fontSize: 13,
            fontFamily: "var(--font-body)",
            fontWeight: 600,
            letterSpacing: "0.04em",
            transition: "background var(--dur-fast)",
          }}
        >
          Sign out
        </button>
      </div>
    </header>
  );
}
