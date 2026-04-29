/**
 * Root application component — owns the route tree.
 *
 * Routes (React Router v6):
 *   /            → redirect to /chat (if authenticated) or /signin
 *   /signin      → SignIn page (public)
 *   /signup      → SignUp page (public)
 *   /chat        → ChatPanel (protected — requires valid JWT)
 *   /runs/:id    → RunDetail (protected — shows tool-call timeline for a run)
 *
 * ProtectedRoute helper:
 *   Reads `isAuthenticated` from AuthContext.  Redirects to /signin when the
 *   user is not logged in.  No flash-of-unauthenticated content: renders a
 *   skeleton until the AuthContext bootstrap check completes.
 *
 * Layout:
 *   Authenticated routes share a persistent top-level NavBar component that
 *   shows the user email and a Sign Out button.
 *
 * Implemented in Stage 7.
 */

import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import SignIn from "./auth/SignIn";
import SignUp from "./auth/SignUp";
import ChatPanel from "./chat/ChatPanel";
import RunDetail from "./runs/RunDetail";

// Placeholder — implemented in Stage 7
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <>{children}</> : <Navigate to="/signin" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/signin" element={<SignIn />} />
      <Route path="/signup" element={<SignUp />} />
      <Route
        path="/chat"
        element={
          <ProtectedRoute>
            <ChatPanel />
          </ProtectedRoute>
        }
      />
      <Route
        path="/runs/:id"
        element={
          <ProtectedRoute>
            <RunDetail />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/chat" replace />} />
    </Routes>
  );
}
