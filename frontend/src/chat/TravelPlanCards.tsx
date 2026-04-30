import type { SseChunk, SseClassification, SseLiveConditions } from "@/api/client";

// ── Retrieve result: destination knowledge cards ──────────────────────────

interface RetrieveCardsProps {
  chunks: SseChunk[];
}

export function RetrieveCards({ chunks }: RetrieveCardsProps) {
  if (!chunks.length) return null;

  // Group chunks by source
  const bySource: Record<string, SseChunk[]> = {};
  for (const c of chunks) {
    const key = c.source ?? "Unknown";
    (bySource[key] ??= []).push(c);
  }

  return (
    <div style={sectionWrap}>
      <SectionLabel icon="📍" label="Retrieved Destinations" color="var(--teal)" />
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {Object.entries(bySource).map(([source, items]) => (
          <div key={source} style={destCard}>
            <div style={destHeader}>
              <span style={destName}>
                {formatSourceName(source)}
              </span>
              {items[0]?.similarity != null && (
                <span style={similarityBadge}>
                  {Math.round(items[0].similarity * 100)}% match
                </span>
              )}
            </div>
            {items.map((chunk) => (
              <div key={chunk.chunk_index} style={chunkRow}>
                {chunk.section && (
                  <span style={sectionTag}>{chunk.section}</span>
                )}
                <p style={chunkText}>{chunk.text}</p>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function formatSourceName(source: string): string {
  return source
    .replace(/_wikivoyage\.md$/, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ── Classify result: travel style badges ──────────────────────────────────

const STYLE_CONFIG: Record<string, { emoji: string; color: string; bg: string }> = {
  Adventure:   { emoji: "🧗", color: "#2d6a2d", bg: "#e8f5e9" },
  Relaxation:  { emoji: "🏖", color: "#1565c0", bg: "#e3f2fd" },
  Culture:     { emoji: "🏛", color: "#6a1565", bg: "#f3e5f5" },
  Budget:      { emoji: "💸", color: "#e65100", bg: "#fff3e0" },
  Luxury:      { emoji: "✨", color: "#c9a84c", bg: "#fffde7" },
  Family:      { emoji: "👨‍👩‍👧", color: "#d81b60", bg: "#fce4ec" },
};

interface ClassifyCardsProps {
  classifications: SseClassification[];
}

export function ClassifyCards({ classifications }: ClassifyCardsProps) {
  if (!classifications.length) return null;

  return (
    <div style={sectionWrap}>
      <SectionLabel icon="🏷" label="Travel Style Analysis" color="#7c5cbf" />
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
        {classifications.map((cls, i) => {
          const cfg = STYLE_CONFIG[cls.label] ?? { emoji: "🌍", color: "var(--ink-muted)", bg: "var(--cream-dark)" };
          return (
            <div key={i} style={{ ...stylePill, color: cfg.color, background: cfg.bg, border: `1px solid ${cfg.color}30` }}>
              <span style={{ fontSize: 20 }}>{cfg.emoji}</span>
              <div>
                <div style={{ fontWeight: 700, fontSize: 15, fontFamily: "var(--font-display)", letterSpacing: "0.02em" }}>
                  {cls.label}
                </div>
                {cls.destination_name && (
                  <div style={{ fontSize: 11, opacity: 0.7, fontFamily: "var(--font-body)" }}>
                    {cls.destination_name}
                  </div>
                )}
                {cls.confidence != null && (
                  <ConfidenceBar value={cls.confidence} color={cfg.color} />
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ConfidenceBar({ value, color }: { value: number; color: string }) {
  return (
    <div style={{ marginTop: 4, display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{ flex: 1, height: 4, background: `${color}22`, borderRadius: 2, overflow: "hidden" }}>
        <div style={{ width: `${Math.round(value * 100)}%`, height: "100%", background: color, borderRadius: 2 }} />
      </div>
      <span style={{ fontSize: 11, opacity: 0.8, fontFamily: "var(--font-body)", fontWeight: 600 }}>
        {Math.round(value * 100)}%
      </span>
    </div>
  );
}

// ── Live conditions: weather, FX, flights ─────────────────────────────────

interface LiveCardsProps {
  liveData: SseLiveConditions[];
  onBookFlight?: (flight: LiveFlightItem, destName: string) => void;
}

type LiveFlightItem = {
  origin?: string;
  destination?: string;
  price?: number;
  currency?: string;
  departure_date?: string;
  airline?: string;
  flight_number?: string;
};

export function LiveCards({ liveData, onBookFlight }: LiveCardsProps) {
  if (!liveData.length) return null;

  return (
    <div style={sectionWrap}>
      <SectionLabel icon="🌤" label="Live Conditions" color="#d4860a" />
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {liveData.map((item, i) => (
          <LiveConditionCard key={i} data={item} onBookFlight={onBookFlight} />
        ))}
      </div>
    </div>
  );
}

function LiveConditionCard({ data, onBookFlight }: { data: SseLiveConditions; onBookFlight?: LiveCardsProps["onBookFlight"] }) {
  return (
    <div style={liveCard}>
      {data.destination_name && (
        <h4 style={{ fontFamily: "var(--font-display)", fontSize: 17, marginBottom: 10, color: "var(--teal)" }}>
          {data.destination_name}
        </h4>
      )}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: data.flights?.length ? 12 : 0 }}>
        {/* Weather */}
        {data.weather && (
          <div style={liveChip}>
            <span style={{ fontSize: 18 }}>🌡</span>
            <div>
              <div style={liveChipLabel}>Weather</div>
              <div style={liveChipValue}>
                {data.weather.temp_c != null && <b>{Math.round(data.weather.temp_c)}°C</b>}
                {data.weather.description && ` · ${data.weather.description}`}
              </div>
              {data.weather.precip_mm != null && (
                <div style={liveChipSub}>Rain: {data.weather.precip_mm}mm · Wind: {data.weather.wind_kph}kph</div>
              )}
            </div>
          </div>
        )}

        {/* FX */}
        {data.fx && (
          <div style={liveChip}>
            <span style={{ fontSize: 18 }}>💱</span>
            <div>
              <div style={liveChipLabel}>Exchange Rate</div>
              <div style={liveChipValue}>
                <b>1 {data.fx.base}</b> = {data.fx.rate?.toFixed(4)} {data.fx.quote}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Flights */}
      {!!data.flights?.length && (
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: "var(--ink-muted)", letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 8, fontFamily: "var(--font-body)" }}>
            Available Flights
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {data.flights.map((f, fi) => (
              <div key={fi} style={flightRow}>
                <div style={{ flex: 1 }}>
                  <span style={{ fontFamily: "var(--font-display)", fontSize: 15, fontWeight: 600 }}>
                    {f.origin} → {f.destination}
                  </span>
                  {f.departure_date && (
                    <span style={{ fontSize: 12, color: "var(--ink-muted)", marginLeft: 8 }}>{f.departure_date}</span>
                  )}
                  {f.airline && (
                    <span style={{ fontSize: 12, color: "var(--ink-muted)", marginLeft: 4 }}>· {f.airline}</span>
                  )}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  {f.price != null && (
                    <span style={{ fontWeight: 700, color: "var(--teal)", fontSize: 15, fontFamily: "var(--font-body)" }}>
                      {f.currency ?? "USD"} {f.price.toLocaleString()}
                    </span>
                  )}
                  {onBookFlight && (
                    <button
                      className="btn btn-gold"
                      style={{ padding: "4px 12px", fontSize: 12 }}
                      onClick={() => onBookFlight(f, data.destination_name ?? "")}
                    >
                      Book
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Answer: formatted travel plan ─────────────────────────────────────────

interface TravelPlanProps {
  text: string;
  streaming?: boolean;
}

export function TravelPlanAnswer({ text, streaming }: TravelPlanProps) {
  if (!text) return null;
  return (
    <div style={answerCard}>
      <div style={answerHeader}>
        <span style={{ fontSize: 20 }}>🗺</span>
        <span style={{ fontFamily: "var(--font-display)", fontSize: 18, letterSpacing: "0.04em" }}>
          Your Travel Plan
        </span>
        {streaming && <span style={streamingDot} />}
      </div>
      <div style={answerBody}>
        {text.split("\n").map((line, i) => {
          if (!line.trim()) return <br key={i} />;
          if (line.startsWith("# ")) return <h2 key={i} style={planH1}>{line.slice(2)}</h2>;
          if (line.startsWith("## ")) return <h3 key={i} style={planH2}>{line.slice(3)}</h3>;
          if (line.startsWith("### ")) return <h4 key={i} style={planH3}>{line.slice(4)}</h4>;
          if (line.startsWith("- ") || line.startsWith("* ")) {
            return <div key={i} style={planBullet}><span style={{ color: "var(--gold)", marginRight: 6 }}>•</span>{line.slice(2)}</div>;
          }
          if (/^\d+\.\s/.test(line)) {
            return <div key={i} style={planBullet}>{line}</div>;
          }
          return <p key={i} style={planPara}>{line}</p>;
        })}
      </div>
    </div>
  );
}

// ── Shared sub-components ─────────────────────────────────────────────────

function SectionLabel({ icon, label, color }: { icon: string; label: string; color: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
      <span style={{ fontSize: 16 }}>{icon}</span>
      <span style={{
        fontFamily: "var(--font-body)",
        fontSize: 12,
        fontWeight: 700,
        letterSpacing: "0.08em",
        textTransform: "uppercase",
        color,
      }}>
        {label}
      </span>
      <div style={{ flex: 1, height: 1, background: `${color}28` }} />
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────

const sectionWrap: React.CSSProperties = {
  animation: "fadeSlideUp 0.4s cubic-bezier(0.4,0,0.2,1) both",
  padding: "14px 16px",
  background: "var(--cream)",
  borderRadius: "var(--r-lg)",
  border: "1px solid var(--border)",
};

const destCard: React.CSSProperties = {
  background: "var(--white)",
  border: "1px solid var(--border)",
  borderRadius: "var(--r-md)",
  padding: "12px 14px",
  boxShadow: "var(--shadow-xs)",
};

const destHeader: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  marginBottom: 8,
};

const destName: React.CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: 16,
  fontWeight: 600,
  color: "var(--teal)",
};

const similarityBadge: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 600,
  fontFamily: "var(--font-body)",
  color: "var(--teal)",
  background: "var(--teal-pale)",
  padding: "2px 8px",
  borderRadius: 999,
};

const chunkRow: React.CSSProperties = {
  marginTop: 8,
  paddingTop: 8,
  borderTop: "1px solid var(--cream-dark)",
};

const sectionTag: React.CSSProperties = {
  display: "inline-block",
  fontSize: 10,
  fontWeight: 700,
  fontFamily: "var(--font-body)",
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "var(--gold)",
  background: "var(--gold-light)",
  padding: "2px 8px",
  borderRadius: 3,
  marginBottom: 4,
};

const chunkText: React.CSSProperties = {
  fontSize: 13,
  color: "var(--ink-muted)",
  lineHeight: 1.55,
  fontFamily: "var(--font-body)",
};

const stylePill: React.CSSProperties = {
  display: "flex",
  alignItems: "flex-start",
  gap: 10,
  padding: "12px 16px",
  borderRadius: "var(--r-md)",
  minWidth: 160,
};

const liveCard: React.CSSProperties = {
  background: "var(--white)",
  border: "1px solid var(--border)",
  borderRadius: "var(--r-md)",
  padding: "14px 16px",
  boxShadow: "var(--shadow-xs)",
};

const liveChip: React.CSSProperties = {
  display: "flex",
  alignItems: "flex-start",
  gap: 8,
  padding: "10px 14px",
  background: "var(--cream)",
  borderRadius: "var(--r-md)",
  border: "1px solid var(--border)",
  minWidth: 160,
};

const liveChipLabel: React.CSSProperties = {
  fontSize: 10,
  fontWeight: 700,
  fontFamily: "var(--font-body)",
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "var(--ink-faint)",
};

const liveChipValue: React.CSSProperties = {
  fontSize: 14,
  fontFamily: "var(--font-body)",
  color: "var(--ink)",
  marginTop: 2,
};

const liveChipSub: React.CSSProperties = {
  fontSize: 11,
  fontFamily: "var(--font-body)",
  color: "var(--ink-muted)",
  marginTop: 2,
};

const flightRow: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "8px 12px",
  background: "var(--cream)",
  border: "1px solid var(--border)",
  borderRadius: "var(--r-md)",
  gap: 8,
};

const answerCard: React.CSSProperties = {
  background: "var(--white)",
  border: "1px solid var(--border)",
  borderRadius: "var(--r-lg)",
  boxShadow: "var(--shadow-sm)",
  overflow: "hidden",
  animation: "fadeSlideUp 0.5s cubic-bezier(0.4,0,0.2,1) both",
};

const answerHeader: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 10,
  padding: "14px 20px",
  background: "var(--teal)",
  color: "white",
};

const streamingDot: React.CSSProperties = {
  width: 8,
  height: 8,
  borderRadius: "50%",
  background: "var(--gold)",
  animation: "pulse 1s ease-in-out infinite",
  marginLeft: 4,
};

const answerBody: React.CSSProperties = {
  padding: "20px 24px",
  maxHeight: 600,
  overflowY: "auto",
};

const planH1: React.CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: 24,
  fontWeight: 500,
  color: "var(--teal)",
  margin: "16px 0 8px",
};

const planH2: React.CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: 20,
  fontWeight: 500,
  color: "var(--ink)",
  margin: "14px 0 6px",
};

const planH3: React.CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: 16,
  fontWeight: 500,
  color: "var(--ink-muted)",
  margin: "10px 0 4px",
};

const planBullet: React.CSSProperties = {
  fontSize: 14,
  fontFamily: "var(--font-body)",
  color: "var(--ink)",
  lineHeight: 1.6,
  paddingLeft: 4,
  marginBottom: 3,
};

const planPara: React.CSSProperties = {
  fontSize: 14,
  fontFamily: "var(--font-body)",
  color: "var(--ink)",
  lineHeight: 1.7,
  marginBottom: 6,
};
