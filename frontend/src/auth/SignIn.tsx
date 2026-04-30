import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { apiClient } from "@/api/client";
import type { LoginResponse } from "@/api/client";
import Spinner from "@/components/Spinner";

export default function SignIn() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await apiClient.post<LoginResponse>("/auth/login", { email, password });
      login(res.data.access_token);
      navigate("/chat", { replace: true });
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } }).response?.status;
      setError(status === 401 ? "Invalid email or password." : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={outerStyle}>
      {/* Decorative strip */}
      <div style={decorStrip} />

      <div style={cardStyle}>
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={logoStyle}>✈</div>
          <h1 style={titleStyle}>Grand Tour</h1>
          <p style={{ color: "var(--ink-muted)", fontSize: 14, fontFamily: "var(--font-body)" }}>
            Your AI-powered travel planner
          </p>
        </div>

        <h2 style={headingStyle}>Welcome back</h2>

        {error && (
          <div role="alert" style={errorStyle}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label htmlFor="email" style={labelStyle}>Email address</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              className="input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label htmlFor="password" style={labelStyle}>Password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading}
            style={{ marginTop: 8, height: 44, fontSize: 15, justifyContent: "center" }}
          >
            {loading ? <Spinner size="sm" color="white" label="Signing in…" /> : "Sign in"}
          </button>
        </form>

        <p style={{ textAlign: "center", marginTop: 24, fontSize: 14, color: "var(--ink-muted)", fontFamily: "var(--font-body)" }}>
          Don't have an account?{" "}
          <Link to="/signup" style={{ color: "var(--teal)", fontWeight: 600, textDecoration: "none" }}>
            Sign up
          </Link>
        </p>
      </div>
    </div>
  );
}

const outerStyle: React.CSSProperties = {
  minHeight: "100vh",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  background: "var(--cream)",
  position: "relative",
  overflow: "hidden",
};

const decorStrip: React.CSSProperties = {
  position: "absolute",
  top: 0,
  left: 0,
  right: 0,
  height: 5,
  background: "linear-gradient(90deg, var(--teal), var(--gold), var(--terracotta))",
};

const cardStyle: React.CSSProperties = {
  background: "var(--white)",
  borderRadius: "var(--r-xl)",
  border: "1px solid var(--border)",
  boxShadow: "var(--shadow-lg)",
  padding: "40px 40px",
  width: "100%",
  maxWidth: 440,
  animation: "fadeSlideUp 0.5s cubic-bezier(0.4,0,0.2,1) both",
};

const logoStyle: React.CSSProperties = {
  width: 56,
  height: 56,
  borderRadius: "50%",
  background: "var(--teal)",
  color: "white",
  fontSize: 24,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  margin: "0 auto 12px",
  boxShadow: "0 4px 16px rgba(26,107,122,0.30)",
};

const titleStyle: React.CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: 28,
  fontWeight: 500,
  color: "var(--teal)",
  letterSpacing: "0.06em",
};

const headingStyle: React.CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: 22,
  fontWeight: 500,
  color: "var(--ink)",
  marginBottom: 20,
};

const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: 13,
  fontWeight: 600,
  color: "var(--ink-muted)",
  marginBottom: 6,
  fontFamily: "var(--font-body)",
  letterSpacing: "0.04em",
  textTransform: "uppercase",
};

const errorStyle: React.CSSProperties = {
  padding: "10px 14px",
  borderRadius: "var(--r-md)",
  background: "#fdf0ef",
  border: "1px solid #f5c2bb",
  color: "var(--error)",
  fontSize: 14,
  fontFamily: "var(--font-body)",
  marginBottom: 4,
};
