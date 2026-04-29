/**
 * Configured axios instance — single HTTP entry point for the entire frontend.
 *
 * Responsibilities:
 *   - Sets `baseURL` from the `VITE_API_BASE_URL` build-time env var (defaults
 *     to `/api`, which the nginx proxy or Vite dev-server proxy forwards to the
 *     FastAPI backend).
 *   - Request interceptor: reads the JWT access token from localStorage and
 *     attaches it as `Authorization: Bearer <token>` on every outgoing request.
 *   - Response interceptor: on HTTP 401 clears the stored token and redirects
 *     the browser to /signin so the user is never left in a broken state.
 *
 * Usage:
 *   import { apiClient } from "@/api/client";
 *   const res = await apiClient.post("/auth/login", { email, password });
 *
 * Implemented in Stage 7.
 */

import axios from "axios";

export const TOKEN_KEY = "stp_access_token";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "/api",
  headers: { "Content-Type": "application/json" },
  timeout: 60_000,
});

// Attach JWT on every request
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// On 401: clear token and redirect to /signin
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      window.location.href = "/signin";
    }
    return Promise.reject(error);
  },
);

// Typed helper wrappers — implemented in Stage 7
export type LoginPayload = { email: string; password: string };
export type LoginResponse = { access_token: string; token_type: string };

export type SignUpPayload = { email: string; password: string };

export type ChatRequest = { question: string; webhook_url?: string };
export type ChatResponse = {
  run_id: string;
  answer: string;
  tools_fired: string[];
};

export type AgentRun = {
  id: string;
  question: string;
  final_answer: string;
  total_tokens_cheap: number;
  total_tokens_strong: number;
  cost_usd: number;
  started_at: string;
  finished_at: string | null;
  tool_calls: ToolCall[];
};

export type ToolCall = {
  id: string;
  tool_name: string;
  args_json: Record<string, unknown>;
  result_json: Record<string, unknown>;
  tokens: number;
  latency_ms: number;
  error: string | null;
  created_at: string;
};
