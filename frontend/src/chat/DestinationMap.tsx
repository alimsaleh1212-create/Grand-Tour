import { useEffect, useRef } from "react";
import L from "leaflet";
import type { SseLiveConditions } from "@/api/client";

interface DestinationMapProps {
  destinations: SseLiveConditions[];
}

const MAP_STYLE: React.CSSProperties = {
  height: 320,
  borderRadius: "var(--r-lg)",
  overflow: "hidden",
  border: "1px solid var(--border)",
};

const STYLE_CONFIG: Record<string, { emoji: string; color: string; bg: string }> = {
  Adventure: { emoji: "🧗", color: "#2d6a2d", bg: "#e8f5e9" },
  Relaxation: { emoji: "🏖", color: "#1565c0", bg: "#e3f2fd" },
  Culture: { emoji: "🏛", color: "#6a1565", bg: "#f3e5f5" },
  Budget: { emoji: "💸", color: "#e65100", bg: "#fff3e0" },
  Luxury: { emoji: "✨", color: "#c9a84c", bg: "#fffde7" },
  Family: { emoji: "👨‍👩‍👧", color: "#d81b60", bg: "#fce4ec" },
};

const DEFAULT_STYLE = { emoji: "🌍", color: "var(--ink-muted)", bg: "var(--cream-dark)" };

function createMarkerIcon(label: string) {
  return L.divIcon({
    className: "",
    iconSize: [28, 36],
    iconAnchor: [14, 36],
    popupAnchor: [0, -38],
    html: `
      <div style="position:relative;width:28px;height:36px;">
        <svg width="28" height="36" viewBox="0 0 28 36" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M14 0C6.27 0 0 6.27 0 14c0 10.5 14 22 14 22s14-11.5 14-22C28 6.27 21.73 0 14 0z" fill="#1A6B7A"/>
          <circle cx="14" cy="13" r="7" fill="white"/>
          <text x="14" y="17" text-anchor="middle" font-size="10">${label}</text>
        </svg>
      </div>
    `,
  });
}

export default function DestinationMap({ destinations }: DestinationMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);

  const validDests = destinations.filter(
    (d) => d.latitude != null && d.longitude != null
  );

  useEffect(() => {
    if (!containerRef.current || validDests.length === 0) return;

    if (mapRef.current) {
      mapRef.current.remove();
      mapRef.current = null;
    }

    const map = L.map(containerRef.current, {
      scrollWheelZoom: false,
      zoomControl: true,
    }).setView([20, 0], 2);

    mapRef.current = map;

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 18,
    }).addTo(map);

    const markers: L.Marker[] = [];

    validDests.forEach((d) => {
      const lat = d.latitude!;
      const lon = d.longitude!;
      const name = d.destination_name || "Destination";

      const style = (d as any).style
        ? STYLE_CONFIG[(d as any).style] ?? DEFAULT_STYLE
        : DEFAULT_STYLE;
      const emoji = style.emoji;

      const marker = L.marker([lat, lon], {
        icon: createMarkerIcon(emoji),
      }).addTo(map);

      const photoUrl = `https://source.unsplash.com/400x300/?${encodeURIComponent(name)},travel`;

      const popup = L.popup({ maxWidth: 280, minWidth: 220 }).setContent(`
        <div style="font-family:Nunito,system-ui,sans-serif;width:260px;">
          <img
            src="${photoUrl}"
            alt="${name}"
            style="width:100%;height:140px;object-fit:cover;border-radius:8px 8px 0 0;"
            onerror="this.style.display='none'"
          />
          <div style="padding:8px 12px;">
            <div style="font-family:Cormorant Garamond,Georgia,serif;font-size:17px;font-weight:600;color:#1A6B7A;">
              ${name}
            </div>
            ${d.weather ? `
              <div style="font-size:13px;color:#4a4a5a;margin-top:4px;">
                🌡 ${Math.round(d.weather.temp_c ?? 0)}°C
                ${d.weather.precip_mm != null ? ` · ${d.weather.precip_mm}mm rain` : ""}
              </div>
            ` : ""}
            ${d.flights && d.flights.length > 0 && d.flights[0].price != null ? `
              <div style="font-size:13px;color:#4a4a5a;margin-top:2px;">
                ✈ ${d.flights[0].currency ?? "USD"} ${d.flights[0].price!.toLocaleString()}
              </div>
            ` : ""}
            <div style="font-size:10px;color:#A8A8B8;margin-top:4px;">
              ${lat.toFixed(2)}°, ${lon.toFixed(2)}°
            </div>
          </div>
        </div>
      `);

      marker.bindPopup(popup);
      markers.push(marker);
    });

    if (markers.length === 1) {
      map.setView(markers[0].getLatLng(), 5);
    } else {
      const group = L.featureGroup(markers);
      map.fitBounds(group.getBounds().pad(0.15));
    }

    setTimeout(() => map.invalidateSize(), 100);

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [validDests.length]);

  if (validDests.length === 0) return null;

  return (
    <div style={sectionWrap}>
      <SectionLabel icon="🗺" label="Destinations Map" color="var(--teal)" />
      <div ref={containerRef} style={MAP_STYLE} />
    </div>
  );
}

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

const sectionWrap: React.CSSProperties = {
  animation: "fadeSlideUp 0.4s cubic-bezier(0.4,0,0.2,1) both",
  padding: "14px 16px",
  background: "var(--cream)",
  borderRadius: "var(--r-lg)",
  border: "1px solid var(--border)",
};