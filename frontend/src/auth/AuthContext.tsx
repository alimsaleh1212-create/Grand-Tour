/**
 * Authentication context — global JWT state shared across the entire tree.
 *
 * Provides:
 *   - `isAuthenticated: boolean`  — true when a valid token is in localStorage.
 *   - `user: { email: string } | null` — decoded claims from the JWT (client-side
 *     only, no extra round-trip needed).
 *   - `login(token: string): void`  — stores token, updates context.
 *   - `logout(): void`              — clears token, redirects to /signin.
 *
 * Bootstrap:
 *   On mount, AuthProvider reads localStorage for an existing token.  If one
 *   exists it is validated with a lightweight `GET /auth/me` call; on 401 the
 *   token is discarded so the user is directed to sign in.
 *
 * Why context (not Zustand / Redux):
 *   Auth state is read by every protected route and the NavBar.  React context
 *   is the idiomatic solution for true cross-cutting singleton state without
 *   adding a state-management dependency.
 *
 * Implemented in Stage 7.
 */

import { createContext, useContext, useState, useEffect } from "react";
import type { ReactNode } from "react";
import { apiClient, TOKEN_KEY } from "@/api/client";

interface AuthState {
  isAuthenticated: boolean;
  user: { email: string } | null;
  login: (token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<{ email: string } | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    // Bootstrap: verify existing token on mount — implemented in Stage 7
    setChecked(true);
  }, []);

  const login = (_token: string) => {
    // Implemented in Stage 7
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
    window.location.href = "/signin";
  };

  if (!checked) return null; // prevent flash before bootstrap completes

  return (
    <AuthContext.Provider
      value={{ isAuthenticated: user !== null, user, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

// suppress unused import warning during scaffolding
void apiClient;
