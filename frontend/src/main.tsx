/**
 * Application entry point.
 *
 * Mounts the React tree into `#root`.  Wraps the app in:
 *   - React.StrictMode (double-invokes effects in dev to surface impurity)
 *   - BrowserRouter (enables React Router v6 declarative routing)
 *   - AuthProvider (global JWT / user state — see auth/AuthContext.tsx)
 *
 * Implemented in Stage 7.
 */

import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
