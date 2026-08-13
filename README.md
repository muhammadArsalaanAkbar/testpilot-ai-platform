# TestPilot AI

AI-powered web application testing platform: point it at a URL, get AI-generated test cases,
run them as real browser sessions, and get AI-explained failure analysis. See
[`specs/001-testpilot-ai-platform/spec.md`](specs/001-testpilot-ai-platform/spec.md) for the
full product specification.

## Repository layout

```text
testpilot-ai/
├── backend/          # FastAPI API, RQ worker, and Typer CLI — one Python package
│   ├── src/testpilot/
│   │   ├── core/       # config, DB session, base models, shared exceptions, middleware
│   │   ├── auth/, orgs/, projects/, testcases/, issues/, reports/,
│   │   │   notifications/, billing/, audit/       # domain libraries (Library-First)
│   │   ├── ai_provider/, ai_generation/, ai_analysis/   # AI generation & failure analysis
│   │   ├── execution/                              # Playwright automation engine + orchestrator
│   │   ├── storage/                                 # object storage (screenshots/logs)
│   │   ├── api/                                      # FastAPI app + HTTP routes (thin layer)
│   │   ├── worker/                                   # RQ worker entrypoints/jobs
│   │   └── cli/                                       # testpilot-cli (Typer)
│   ├── alembic/       # DB migrations
│   └── tests/         # unit / integration / contract
├── frontend/          # Next.js (App Router) + TypeScript + Tailwind dashboard
├── infra/
│   ├── docker/         # Dockerfiles + docker-compose for local dev
│   └── k8s/            # Kubernetes manifests (base + overlays)
├── specs/001-testpilot-ai-platform/   # spec.md, plan.md, tasks.md, and all design artifacts
└── .specify/           # Spec Kit configuration, templates, constitution
```

## Spec-Driven Development workflow

This project is built with [Spec Kit](https://github.com/github/spec-kit). The governing
sequence is:

```
/speckit-constitution → /speckit-specify → /speckit-plan → /speckit-tasks
  → /speckit-analyze → /speckit-implement
```

- **Constitution**: `.specify/memory/constitution.md` — non-negotiable project principles.
- **Spec**: `specs/001-testpilot-ai-platform/spec.md` — what to build and why.
- **Plan**: `specs/001-testpilot-ai-platform/plan.md` — architecture and technical decisions
  (see also `research.md`, `data-model.md`, `contracts/`, `quickstart.md`).
- **Tasks**: `specs/001-testpilot-ai-platform/tasks.md` — the dependency-ordered task list this
  codebase is being implemented from. Task IDs referenced in commits/PRs (e.g. `T090`) trace
  back to this file.

Every PR should verify compliance with the Core Principles in the constitution before merge.

## Local development

See [`specs/001-testpilot-ai-platform/quickstart.md`](specs/001-testpilot-ai-platform/quickstart.md)
for the full local setup and end-to-end validation guide. Short version:

```sh
# Backend
cd backend
uv sync --extra dev
cp ../infra/docker/.env.example .env   # then edit values for local use
uv run alembic upgrade head
uv run uvicorn testpilot.api.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

Or bring up the full stack (Postgres, Redis, MinIO, API, worker, frontend) at once:

```sh
docker compose -f infra/docker/docker-compose.yml up
```

## Testing

```sh
# Backend
cd backend && uv run pytest

# Frontend
cd frontend && npm test        # unit (Vitest)
cd frontend && npm run e2e     # end-to-end (Playwright Test)
```
