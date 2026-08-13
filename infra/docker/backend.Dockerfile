# Shared image for the `api` and `worker` deployables (plan.md's
# Containerization & Kubernetes readiness / research.md #16): same backend
# Python package, different CMD selects the role. Build context is the
# repo root (docker-compose.yml sets `context: ../..`), not `backend/`
# alone, so this file can also COPY infra/docker/backend-entrypoint.sh —
# every path below is repo-root-relative.

# --- deps stage: install dependencies only, before the app's own source
# changes, so this layer stays cached across ordinary code edits ---
FROM python:3.12-slim AS deps

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
# --no-install-project: the project itself isn't copied in yet (see below),
# so this layer only resolves and installs third-party dependencies — the
# expensive, rarely-changing part.
RUN uv sync --frozen --no-dev --no-install-project

# --- build stage: install the project itself on top of the cached deps ---
FROM deps AS build

COPY backend/src/ ./src/
RUN uv sync --frozen --no-dev

# --- runtime stage: no uv, no build tooling — just the venv, source, and
# Playwright's browser runtime ---
FROM python:3.12-slim AS runtime

# Playwright's own CLI resolves and installs exactly the OS packages its
# bundled Chromium build needs for the current base image, rather than
# this Dockerfile hand-maintaining that list — must run as root (apt), so
# it happens before the non-root user is created below. The `execution`
# library (browser automation engine) needs a real Chromium; no
# mocked/fake browser exists in the production job path.
#
# PLAYWRIGHT_BROWSERS_PATH is set explicitly, to a location outside any
# per-user home directory, and BEFORE this install step — without it,
# `playwright install` (run here as root) downloads browsers into root's
# own cache (`/root/.cache/ms-playwright`), but the process actually runs
# at runtime as the non-root `testpilot` user created below, whose own
# cache directory is empty — every real browser-automation call then fails
# with "Executable doesn't exist", silently masked by NFR-007's per-step
# fault isolation (a test case's engine exception is caught and recorded
# as that case's own `error` result, not surfaced as a job failure) until
# actually observed end-to-end (found during Phase 26 E2E validation).
# Setting the SAME env var again after `USER testpilot` (it's already
# inherited, but restated for clarity) ensures both the install step and
# every later `chromium.launch()` call agree on one shared, root-writable-
# at-build-time-but-world-readable-at-runtime location.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
COPY --from=build /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
RUN playwright install --with-deps chromium && chmod -R a+rX /ms-playwright

RUN groupadd --system testpilot && useradd --system --gid testpilot --create-home testpilot
WORKDIR /app
COPY --chown=testpilot:testpilot backend/src/ ./src/
COPY --chown=testpilot:testpilot backend/alembic/ ./alembic/
COPY --chown=testpilot:testpilot backend/alembic.ini ./
COPY --chown=testpilot:testpilot infra/docker/backend-entrypoint.sh /usr/local/bin/backend-entrypoint.sh
RUN chmod +x /usr/local/bin/backend-entrypoint.sh

USER testpilot
EXPOSE 8000

# quickstart.md Section 2: "Alembic migrations apply automatically on
# api/worker container start in the dev compose file" — the entrypoint
# runs them before handing off to whichever CMD this container was given
# (gunicorn for `api`, `testpilot-worker` for `worker`, overridden per
# service in docker-compose.yml).
ENTRYPOINT ["backend-entrypoint.sh"]
CMD ["gunicorn", "testpilot.api.main:app", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
