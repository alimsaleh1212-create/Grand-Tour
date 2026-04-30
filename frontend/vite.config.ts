/**
 * Vite configuration for the Smart Travel Planner SPA.
 *
 * Dev server:
 *   - Runs on port 5173.
 *   - Proxies `/api` to the FastAPI backend (http://localhost:8000) so the
 *     browser never needs CORS during local development.
 *
 * Production build:
 *   - Outputs to `dist/`; served by the nginx container defined in Dockerfile.
 *   - The nginx.conf file handles the `/api` → backend proxy at runtime.
 *
 * Alias `@` → `src/` mirrors the tsconfig path mapping so both TypeScript and
 * Vite resolve `@/api/client` identically.
 */

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
