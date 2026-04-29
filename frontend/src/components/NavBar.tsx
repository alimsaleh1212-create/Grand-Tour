/**
 * NavBar — persistent top navigation bar rendered in all authenticated layouts.
 *
 * Contents (left to right):
 *   - "✈ Smart Travel Planner" logo/title (links to /chat).
 *   - Spacer.
 *   - Logged-in user's email (truncated to 24 chars on small screens).
 *   - "Sign out" button — calls `useAuth().logout()`.
 *
 * Design:
 *   Sticky (position: sticky; top: 0) so it stays visible when the message
 *   list scrolls.  Uses a subtle box-shadow to separate from content.
 *
 * Implemented in Stage 7.
 */

import { useAuth } from "@/auth/AuthContext";

export default function NavBar() {
  const { user, logout } = useAuth();
  // Implemented in Stage 7
  return (
    <nav>
      <span>✈ Smart Travel Planner</span>
      <span>{user?.email}</span>
      <button onClick={logout}>Sign out</button>
    </nav>
  );
}
