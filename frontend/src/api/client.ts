import axios from "axios";

export const TOKEN_KEY = "stp_access_token";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "/api",
  headers: { "Content-Type": "application/json" },
  timeout: 60_000,
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

apiClient.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      window.location.href = "/signin";
    }
    return Promise.reject(err);
  },
);

// ── Auth ──────────────────────────────────────────────────────────────────
export type LoginPayload = { email: string; password: string };
export type LoginResponse = { access_token: string; token_type: string };
export type SignUpPayload = { email: string; password: string };
export type MeResponse = { id: number; email: string };

// ── Runs ──────────────────────────────────────────────────────────────────
export type ToolCallOut = {
  id: number;
  tool_name: string;
  args_json: Record<string, unknown>;
  result_json: Record<string, unknown>;
  tokens: number;
  latency_ms: number;
  error: string | null;
  created_at: string;
};

export type RunOut = {
  id: number;
  question: string;
  final_answer: string | null;
  status: string;
  total_tokens_cheap: number;
  total_tokens_strong: number;
  cost_usd: string;
  started_at: string;
  finished_at: string | null;
};

export type RunDetailOut = RunOut & { tool_calls: ToolCallOut[] };

// ── Chat ──────────────────────────────────────────────────────────────────
export type ChatRequest = { question: string; webhook_url?: string };

export type ChatResponse = {
  run_id: number;
  answer: string;
  tools_fired: Array<{ tool_name: string; ok: boolean; latency_ms: number }>;
  cost_usd: number;
  tokens_cheap: number;
  tokens_strong: number;
};

// ── SSE Event types ───────────────────────────────────────────────────────
export type SseChunk = {
  source: string;
  chunk_index: number;
  text: string;
  section?: string;
  similarity?: number;
};

export type SseClassification = {
  label: string;
  confidence: number;
  destination_name?: string;
};

export type SseLiveConditions = {
  destination_name?: string;
  weather?: {
    description?: string;
    temp_c?: number;
    precip_mm?: number;
    wind_kph?: number;
  };
  fx?: { base?: string; quote?: string; rate?: number };
  flights?: Array<{
    origin?: string;
    destination?: string;
    price?: number;
    currency?: string;
    departure_date?: string;
    airline?: string;
    flight_number?: string;
  }>;
};

export type SseEvent =
  | { type: "start"; question: string }
  | { type: "retrieve_result"; chunks: SseChunk[] }
  | { type: "classify_result"; classifications: SseClassification[] }
  | { type: "live_result"; live_data: SseLiveConditions[] }
  | { type: "answer"; text: string }
  | { type: "booking_request"; flight: Record<string, unknown> }
  | { type: "done"; run_id: number; cost_usd: number; errors: string[] }
  | { type: "error"; detail: string };

// ── Bookings ──────────────────────────────────────────────────────────────
export type BookingRequest = {
  run_id?: number;
  origin_iata: string;
  destination_iata: string;
  departure_date: string;
  passenger_name: string;
  passenger_email: string;
  price_total: number;
  currency: string;
};

export type BookingOut = {
  id: number;
  booking_ref: string;
  origin_iata: string;
  destination_iata: string;
  departure_date: string;
  passenger_name: string;
  price_total: string;
  currency: string;
  status: string;
  created_at: string;
};

// ── SSE streaming helper ──────────────────────────────────────────────────
export async function* streamChat(
  body: ChatRequest,
  signal?: AbortSignal,
): AsyncGenerator<SseEvent> {
  const token = localStorage.getItem(TOKEN_KEY);
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api";

  const res = await fetch(`${baseUrl}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`HTTP ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const payload = line.slice(6).trim();
        if (payload) {
          try {
            yield JSON.parse(payload) as SseEvent;
          } catch {
            // skip malformed frames
          }
        }
      }
    }
  }
}
