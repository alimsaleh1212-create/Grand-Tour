# Multi-stage Dockerfile for the React + Vite SPA.
#
# Stage 1 — builder
#   Installs Node dependencies and runs `vite build`, producing a static bundle
#   in /app/dist.  Uses node:20-alpine for a small image.
#
# Stage 2 — runtime
#   Copies only the dist/ artefacts into an nginx:alpine image.  The final
#   image is ~30 MB and contains no source, node_modules, or build tools.
#   The nginx.conf is copied in to wire up the SPA fallback and API proxy.
#
# Build args:
#   VITE_API_BASE_URL  — injected at build time so the axios client has the
#                         correct base URL in the bundled JS.  Defaults to
#                         /api (relative, works with the nginx proxy).

# ─── Stage 1: builder ─────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

COPY . .
RUN npm run build

# ─── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
