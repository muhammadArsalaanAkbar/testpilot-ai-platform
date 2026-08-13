# Multi-stage Next.js production build (research.md #16). Built from repo
# root with this file's directory as build context (docker-compose.yml
# sets `context: ../../frontend`), so paths below are relative to
# `frontend/`.

# --- deps stage: install dependencies only, cached across ordinary code
# edits ---
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# --- builder stage: production build, standalone output (next.config.ts)
# bundles the minimal node_modules subset it needs into
# .next/standalone/node_modules — nothing from this stage's own
# node_modules is copied into the runtime stage below ---
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# The build reads NEXT_PUBLIC_* values at build time (they end up inlined
# into the client bundle, not read from the environment at runtime, so
# there is no way to change it later short of rebuilding) — a build ARG,
# not a hardcoded value, so a CI/deployment pipeline building this image
# for a real (non-localhost) environment can override it via
# `--build-arg`; the default reproduces exactly what quickstart.md's
# docker-compose stack already exposes the API on, so plain local
# `docker compose build` behavior is unchanged.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
RUN npm run build

# --- runtime stage: just the standalone server, static assets, and public
# files — no npm, no source, no full node_modules ---
FROM node:20-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production PORT=3200 HOSTNAME=0.0.0.0

RUN addgroup --system testpilot && adduser --system --ingroup testpilot testpilot

# No public/ directory exists in this project yet (no static assets added
# so far) — nothing to copy there; add a COPY line for it if/when one is.
COPY --from=builder --chown=testpilot:testpilot /app/.next/standalone ./
COPY --from=builder --chown=testpilot:testpilot /app/.next/static ./.next/static

USER testpilot
EXPOSE 3200
CMD ["node", "server.js"]
