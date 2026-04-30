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
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      setChecked(true);
      return;
    }
    // Validate token with a lightweight /auth/me call
    apiClient
      .get<{ email: string }>("/auth/me")
      .then((res) => setUser({ email: res.data.email }))
      .catch(() => localStorage.removeItem(TOKEN_KEY))
      .finally(() => setChecked(true));
  }, []);

  const login = (token: string) => {
    localStorage.setItem(TOKEN_KEY, token);
    // Decode email from JWT payload (client-side only, no extra round-trip)
    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      setUser({ email: payload.sub ?? payload.email ?? "user" });
    } catch {
      setUser({ email: "user" });
    }
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
    window.location.href = "/signin";
  };

  if (!checked) return null;

  return (
    <AuthContext.Provider value={{ isAuthenticated: user !== null, user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
