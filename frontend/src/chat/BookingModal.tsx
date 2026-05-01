import { useState, type FormEvent } from "react";
import { apiClient } from "@/api/client";
import type { BookingOut } from "@/api/client";
import Spinner from "@/components/Spinner";
import { useAuth } from "@/auth/AuthContext";

interface FlightInfo {
  origin?: string;
  origin_city?: string;
  destination?: string;
  destination_city?: string;
  destination_airport?: string;
  departure_time?: string;
  arrival_time?: string;
  duration_hours?: number;
  frequency?: string;
  airline?: string;
  price?: number;
  currency?: string;
  available?: boolean;
  reason?: string;
}

interface Props {
  flight: FlightInfo;
  runId?: number;
  onClose: () => void;
  onBooked: (booking: BookingOut) => void;
}

export default function BookingModal({ flight, runId, onClose, onBooked }: Props) {
  const { user } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState(user?.email ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState<BookingOut | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await apiClient.post<BookingOut>("/bookings", {
        run_id: runId ?? null,
        origin_iata: (flight.origin ?? "???").toUpperCase().slice(0, 3),
        destination_iata: (flight.destination ?? "???").toUpperCase().slice(0, 3),
        departure_date: new Date().toISOString().slice(0, 10),
        passenger_name: name,
        passenger_email: email,
        price_total: flight.price ?? 0,
        currency: flight.currency ?? "USD",
      });
      setConfirmed(res.data);
      onBooked(res.data);
    } catch {
      setError("Booking failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={overlay} onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={modal}>
        {/* Header */}
        <div style={header}>
          <div>
            <div style={{ fontFamily: "var(--font-display)", fontSize: 22, letterSpacing: "0.04em", color: "var(--ink)" }}>
              Confirm Your Flight
            </div>
            <div style={{ fontSize: 13, color: "var(--ink-muted)", marginTop: 2, fontFamily: "var(--font-body)" }}>
              Demo booking — no real ticket is issued
            </div>
          </div>
          <button onClick={onClose} style={closeBtn} aria-label="Close">✕</button>
        </div>

        {/* Flight summary */}
        <div style={flightSummary}>
          <div style={routeDisplay}>
            <span style={iataCode}>{flight.origin ?? "???"}</span>
            <span style={routeArrow}>→</span>
            <span style={iataCode}>{flight.destination ?? "???"}</span>
          </div>
          {(flight.origin_city || flight.destination_city) && (
            <div style={{ fontSize: 13, opacity: 0.85, fontFamily: "var(--font-body)" }}>
              {flight.origin_city ?? ""}{flight.origin_city && flight.destination_city ? " to " : ""}{flight.destination_city ?? ""}
            </div>
          )}
          <div style={flightMeta}>
            {flight.departure_time && <span>dep {flight.departure_time}</span>}
            {flight.arrival_time && <span>arr {flight.arrival_time}</span>}
            {flight.duration_hours != null && <span>{flight.duration_hours}h</span>}
            {flight.airline && <span>✈ {flight.airline}</span>}
            {flight.frequency && <span>{flight.frequency}</span>}
          </div>
          {flight.price != null && (
            <div style={priceDisplay}>
              {flight.currency ?? "USD"} {flight.price.toLocaleString()}
            </div>
          )}
        </div>

        {confirmed ? (
          <div style={successBox}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>✅</div>
            <div style={{ fontFamily: "var(--font-display)", fontSize: 20, marginBottom: 6, color: "var(--teal)" }}>
              Booking Confirmed!
            </div>
            <div style={{ fontSize: 13, color: "var(--ink-muted)", fontFamily: "var(--font-body)" }}>
              Reference: <b style={{ color: "var(--ink)", fontFamily: "monospace" }}>{confirmed.booking_ref}</b>
            </div>
            <button className="btn btn-primary" style={{ marginTop: 20 }} onClick={onClose}>
              Close
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16, padding: "0 24px 24px" }}>
            {error && (
              <div role="alert" style={errorStyle}>{error}</div>
            )}

            <div>
              <label htmlFor="pax-name" style={labelStyle}>Passenger Name</label>
              <input
                id="pax-name"
                type="text"
                required
                minLength={2}
                className="input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Full name as on passport"
              />
            </div>

            <div>
              <label htmlFor="pax-email" style={labelStyle}>Email Address</label>
              <input
                id="pax-email"
                type="email"
                required
                className="input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
              />
            </div>

            <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
              <button type="button" className="btn btn-ghost" style={{ flex: 1, justifyContent: "center" }} onClick={onClose}>
                Cancel
              </button>
              <button type="submit" className="btn btn-gold" style={{ flex: 2, justifyContent: "center", height: 44 }} disabled={loading}>
                {loading ? <Spinner size="sm" label="Booking…" /> : "Confirm Booking"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

const overlay: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  background: "rgba(30,30,42,0.45)",
  backdropFilter: "blur(4px)",
  zIndex: 200,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: 20,
  animation: "fadeIn 0.2s ease",
};

const modal: React.CSSProperties = {
  background: "var(--white)",
  borderRadius: "var(--r-xl)",
  boxShadow: "var(--shadow-lg)",
  width: "100%",
  maxWidth: 480,
  border: "1px solid var(--border)",
  animation: "fadeSlideUp 0.3s cubic-bezier(0.4,0,0.2,1) both",
  overflow: "hidden",
};

const header: React.CSSProperties = {
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  padding: "24px 24px 0",
  marginBottom: 16,
};

const closeBtn: React.CSSProperties = {
  background: "var(--cream)",
  border: "1px solid var(--border)",
  borderRadius: "50%",
  width: 32,
  height: 32,
  cursor: "pointer",
  fontSize: 14,
  color: "var(--ink-muted)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  flexShrink: 0,
};

const flightSummary: React.CSSProperties = {
  margin: "0 24px 20px",
  padding: 16,
  background: "var(--teal)",
  borderRadius: "var(--r-lg)",
  color: "white",
  textAlign: "center",
};

const routeDisplay: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: 12,
  marginBottom: 8,
};

const iataCode: React.CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: 32,
  fontWeight: 600,
  letterSpacing: "0.1em",
};

const routeArrow: React.CSSProperties = {
  fontSize: 20,
  opacity: 0.7,
};

const flightMeta: React.CSSProperties = {
  display: "flex",
  justifyContent: "center",
  gap: 12,
  fontSize: 12,
  opacity: 0.85,
  fontFamily: "var(--font-body)",
  flexWrap: "wrap",
};

const priceDisplay: React.CSSProperties = {
  marginTop: 8,
  fontSize: 20,
  fontWeight: 700,
  fontFamily: "var(--font-body)",
  color: "var(--gold-light)",
};

const successBox: React.CSSProperties = {
  padding: "0 24px 28px",
  textAlign: "center",
};

const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: 12,
  fontWeight: 700,
  color: "var(--ink-muted)",
  marginBottom: 6,
  fontFamily: "var(--font-body)",
  letterSpacing: "0.06em",
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
};
