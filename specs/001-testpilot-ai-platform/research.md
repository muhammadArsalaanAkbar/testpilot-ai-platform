# Phase 0 Research: TestPilot AI

**Feature**: `001-testpilot-ai-platform` | **Date**: 2026-08-05

This document resolves every open engineering decision implied by the Technical Context in
`plan.md`. The high-level stack (Next.js + TypeScript, Tailwind, FastAPI, PostgreSQL, SQLModel,
Playwright, Docker, Kubernetes-ready) was mandated by the spec's Technology Direction input;
the decisions below fill in the specific libraries, patterns, and tradeoffs needed to turn that
direction into a buildable plan. Each entry follows Decision / Rationale / Alternatives
Considered.

---

## 1. Backend web framework & server

**Decision**: FastAPI on an async SQLAlchemy 2.0 engine (via SQLModel), served by Uvicorn
workers behind Gunicorn's process manager in production (`gunicorn -k uvicorn.workers.UvicornWorker`).

**Rationale**: Mandated by spec Technology Direction. Async-native FastAPI matches the
I/O-bound nature of the workload (DB queries, AI provider calls, object storage calls) without
needing a separate async framework migration later. Gunicorn+Uvicorn is the standard
production pattern for process-level resilience (worker restarts) that plain `uvicorn` alone
doesn't provide.

**Alternatives considered**: Plain Uvicorn (rejected — no multi-process supervision in prod);
Django/DRF (rejected — heavier, sync-first, not requested); Flask (rejected — no native async,
no built-in request/response validation).

## 2. Data layer & migrations

**Decision**: SQLModel (SQLAlchemy 2.0 + Pydantic) as the ORM/schema layer, `asyncpg` as the
PostgreSQL driver, Alembic for versioned migrations, `pydantic-settings` for typed configuration.

**Rationale**: SQLModel is mandated by spec Technology Direction and gives one model definition
reused for both DB schema and API request/response validation (NFR-017's "explicit, enforced
types at the API boundary"). Alembic is the de facto migration tool for SQLAlchemy-based
projects; SQLModel does not ship its own migration tool, so pairing with Alembic is standard
practice rather than an added dependency of convenience.

**Alternatives considered**: Raw SQLAlchemy + separate Pydantic schemas (rejected — duplicates
model definitions, more code to keep in sync); Prisma/Python client (rejected — not
Python-native, smaller ecosystem fit for FastAPI); Django ORM (rejected — pulls in Django).

## 3. Authentication & session strategy

**Decision**: Email/password authentication with Argon2id password hashing (`argon2-cffi` via
`passlib`). Short-lived signed JWT access tokens (~15 min) plus rotating opaque refresh tokens
stored server-side (hashed) and delivered as an httpOnly, secure, `SameSite=Lax` cookie. Logout
and idle-expiry (FR-003, FR-008) revoke the refresh token record; access tokens naturally expire
within minutes, bounding the blast radius of a leaked access token.

**Rationale**: Meets SEC-001/SEC-002 (modern adaptive hashing, secure expiring sessions) while
keeping the MVP to one auth method (FR-001–FR-010) with an explicit extension point for SSO
later (FR-011) — SSO would add providers behind the same session-issuance path, not replace it.
Server-side-revocable refresh tokens are required because JWTs alone cannot be invalidated on
logout, which FR-003 explicitly requires.

**Alternatives considered**: Pure stateless JWT with long expiry (rejected — cannot satisfy
FR-003 logout invalidation without a blocklist, which is the same complexity as tracking refresh
tokens but with worse security properties); third-party auth-as-a-service (rejected for MVP —
adds an external dependency/cost the spec did not request and reduces control over the
Organization-scoping model in FR-012–FR-015); pure server-side session cookies with no JWT
(viable alternative, rejected only because JWT access tokens simplify stateless verification in
the worker/CLI paths that also need to act on behalf of a user).

## 4. Multi-tenant data isolation enforcement

**Decision**: Defense in depth. (a) Every tenant-owned table carries a non-nullable
`organization_id` column. (b) A FastAPI dependency resolves `current_organization_id` from the
authenticated session and every repository/query function requires it as an explicit parameter
— there is no code path that queries tenant tables without it. (c) PostgreSQL Row-Level Security
(RLS) policies mirror the same `organization_id` scoping as a second, database-enforced layer,
using a `SET LOCAL app.current_org_id` set per request/transaction.

**Rationale**: DATA-001 and SEC-011 treat cross-tenant leakage as unacceptable, and FR-014 /
FR-138 require it to fail closed even under adversarial ID guessing. Application-layer scoping
alone is one bug away from a leak (a forgotten `WHERE organization_id = ...`); RLS makes a
forgotten filter fail safe instead of leaking data. This is not premature complexity — it is a
direct, traceable response to explicit constitution-adjacent security requirements in the spec,
not a speculative addition.

**Alternatives considered**: Schema-per-tenant or database-per-tenant (rejected — operationally
heavy for the MVP's "personal Organization per signup" model, better suited to a much larger
Enterprise tier that isn't in scope yet); application-layer scoping only, no RLS (rejected —
insufficient defense-in-depth given SEC-011's "fail closed" requirement).

## 5. Background jobs & queue

**Decision**: Redis + RQ (Redis Queue) for the MVP. Three logical queues: `ai-generation`,
`test-execution`, `ai-analysis`, each consumed by dedicated worker processes so a burst of one
job type cannot starve another.

**Rationale**: NFR-004–NFR-006 require execution to run out-of-band from the request/response
cycle and to scale by adding workers. RQ is Python-native, simple to operate, and sufficient for
the MVP's throughput needs; Redis is already needed for rate limiting (SEC-009) and caching
(NFR-008), so it introduces no new infrastructure dependency. Per the constitution's Simplicity
principle, adopting Celery's heavier feature set (routing, chords, multiple brokers) is not
justified until RQ's simpler model is demonstrated insufficient.

**Alternatives considered**: Celery (rejected for MVP — materially more operational complexity
for capabilities not yet needed; documented as the natural upgrade path if queue semantics
outgrow RQ); cloud-managed queue e.g. AWS SQS (rejected for MVP — adds a cloud-provider lock-in
decision the spec doesn't require yet; revisit at the Kubernetes/production-scale phase);
in-process background tasks (`BackgroundTasks`) (rejected — cannot survive an API process
restart mid-execution, and cannot scale independently of the API per NFR-005).

## 6. Browser automation execution model

**Decision**: Playwright for Python (`playwright` package), invoked from worker processes (not
the API process). Each `TestCase` execution runs in its own isolated `BrowserContext` (fresh
cookies/storage per FR-067), created from a shared, pre-warmed `Browser` instance per worker
process to amortize browser-launch cost across a run's test cases.

**Rationale**: Playwright is mandated by spec Technology Direction and directly supports the
required interaction/assertion primitives (FR-059–FR-064). Running it in workers (not inline in
API requests) is required by NFR-004. Context-per-test-case (not browser-per-test-case) is the
standard Playwright pattern for isolation without the overhead of a full browser process per
test, keeping FR-066 timeouts and FR-075 fault isolation cheap to implement.

**Alternatives considered**: Selenium (rejected — spec mandates Playwright); one Browser process
per test case (rejected — unnecessary overhead per FR-068's extensibility goal without a
performance requirement forcing it); Playwright's own test runner (`@playwright/test`) as the
execution engine (rejected — it is a test-authoring/CLI tool for a fixed test suite, not designed
to execute a dynamically generated, per-tenant set of test cases from application-controlled
data; the plan uses the Playwright *library* driven directly by TestPilot's own execution
orchestrator instead).

## 7. AI/LLM provider integration

**Decision**: An internal `LLMProvider` interface (Python `Protocol`) with three operations:
`generate_test_cases(...)`, `analyze_failure(...)`, `chat(...)` (the last for the future AI QA
Assistant). Concrete adapters implement the protocol per provider; the active provider is
selected at startup via configuration (`AI_PROVIDER` env var), never hard-coded into callers.

**Rationale**: Directly satisfies NFR-018 and INT-002 ("provider-agnostic," "swappable via
configuration"). Keeping the interface to exactly the operations the spec requires (test
generation, failure analysis, chat) avoids designing a speculative general-purpose LLM
abstraction beyond what's needed (Simplicity principle).

**Alternatives considered**: Direct SDK calls to a single provider scattered across call sites
(rejected — violates NFR-018 outright); a heavyweight third-party LLM-abstraction framework
(rejected — spec asks for a provider-agnostic *interface*, not a specific abstraction library;
a thin internal Protocol is simpler and fully sufficient).

## 8. Object/artifact storage

**Decision**: S3-compatible object storage accessed through an internal `ArtifactStorage`
interface, backed by AWS S3 (or equivalent) in production and MinIO in local development /
CI, via the `boto3` S3 client (works against both).

**Rationale**: DATA-002 requires artifacts to live outside the relational database. An
interface (mirroring the LLMProvider pattern) keeps the storage backend swappable, and
MinIO's S3-compatible API means local development and CI need no cloud credentials.

**Alternatives considered**: Storing screenshots as DB bytea columns (rejected — explicitly
disallowed by DATA-002 and would not scale); a cloud-specific SDK without an internal interface
(rejected — couples the whole codebase to one storage vendor).

## 9. Frontend application structure

**Decision**: Next.js App Router (TypeScript), server components for initial data-heavy reads
(project lists, reports) where feasible, client components for interactive/real-time views (test
run monitor, test case editor, AI assistant chat). Tailwind CSS with a small set of accessible,
unstyled primitives (Radix UI) as the base for buttons/dialogs/menus/tables, styled via Tailwind
utility classes (shadcn/ui-style conventions, not the shadcn package itself as a hard
dependency).

**Rationale**: Matches spec Technology Direction. App Router server components reduce
client-side JS for read-heavy dashboard/report views (NFR-001), while client components are
reserved for genuinely interactive surfaces. Radix primitives directly support NFR-013/NFR-014
(keyboard operability, semantic markup) without hand-building accessible dropdowns/dialogs from
scratch.

**Alternatives considered**: Pages Router (rejected — App Router is the current Next.js
direction and fits the server/client component split naturally); a full pre-built component
library (e.g., MUI, Ant Design) (rejected — heavier visual opinion works against UX-001's
"premium, not generic-CRUD" requirement; unstyled primitives + Tailwind gives full control).

## 10. Frontend data fetching & state management

**Decision**: TanStack Query (React Query) for all server-state (API data fetching, caching,
mutation, polling). Local/UI-only state (form drafts, panel open/closed) uses React's built-in
state; no global client-state store (Redux/Zustand) is introduced for the MVP.

**Rationale**: Nearly all frontend state in this product *is* server state (projects, test
cases, runs, results, issues); TanStack Query's caching and polling primitives directly serve
FR-071's live test-run status requirement and UX-004's progress indicators without hand-rolled
fetch/poll logic. Introducing a separate global client-state library is unjustified duplication
per the constitution's Simplicity principle when nearly all state already has a home in the
query cache.

**Alternatives considered**: Redux Toolkit (rejected — mostly redundant with TanStack Query for
this data shape); SWR (viable alternative to TanStack Query; TanStack Query chosen for its more
built-out mutation and polling API, no functional gap that favors SWR here).

## 11. Live test run status delivery

**Decision**: MVP uses short-interval polling (TanStack Query `refetchInterval`, e.g. 2s while a
run is in a non-terminal state, stopping automatically on completion) rather than WebSockets or
Server-Sent Events.

**Rationale**: Satisfies FR-071/UX-004 without adding realtime transport infrastructure
(connection management, horizontal-scaling-aware pub/sub) to the MVP. Polling is simple,
stateless, and fully compatible with horizontal API scaling (NFR-005) with no sticky-session
concerns. Explicitly documented as a Future upgrade (WebSocket/SSE via a pub/sub layer such as
Redis) once concurrent-run volume makes polling overhead material — consistent with the spec's
own Future Scope framing for parallel execution (FR-077).

**Alternatives considered**: WebSockets from day one (rejected for MVP — real complexity
(connection affinity, reconnect handling, horizontal scaling) not justified until parallel,
high-volume runs exist per NFR-005/FR-077, which are themselves Future Scope).

## 12. Rate limiting

**Decision**: `slowapi` (a Redis-backed rate-limiting library for Starlette/FastAPI), applied at
the endpoint level to authentication, AI generation/analysis, and test-execution-trigger
endpoints (SEC-009, FR-132), using the same Redis instance as the job queue.

**Rationale**: Redis-backed limits work correctly across multiple API process instances (unlike
in-memory counters), which is required as soon as the API scales horizontally (NFR-005).

**Alternatives considered**: In-memory rate limiting (rejected — incorrect once more than one
API instance is running, which is an MVP-day-one deployment reality, not a future concern);
API-gateway-level rate limiting only (deferred as a defense-in-depth *addition* at the
infrastructure layer once a gateway is chosen — not a replacement for application-level limits,
which must work even if no gateway sits in front yet).

## 13. Observability stack

**Decision**: Structured JSON logging via Python's stdlib `logging` configured with a JSON
formatter (no heavyweight logging framework needed), a request-correlation-ID middleware
(propagated into worker jobs via the job payload), Prometheus-format metrics exposed at
`/metrics` via `prometheus-fastapi-instrumentator`, and an error-tracking SDK (Sentry, chosen as
a concrete, swappable default) for unhandled exceptions in both API and worker processes.

**Rationale**: Directly satisfies NFR-009–NFR-012 and FR-138 (structured logs, metrics, health
checks, error capture with context). Prometheus format is the de facto standard scraped by both
common self-hosted setups and most managed Kubernetes monitoring stacks, supporting the
Kubernetes-readiness requirement without committing to a specific hosted monitoring vendor.

**Alternatives considered**: A dedicated structured-logging framework (e.g., `structlog`)
(reasonable alternative; stdlib `logging` + a JSON formatter chosen to avoid an extra dependency
where the standard library already meets the requirement — Simplicity principle. `structlog` is
noted as an acceptable substitution at implementation time if richer structured-logging
ergonomics are wanted).

## 14. Testing tooling

**Decision**: Backend — `pytest` + `pytest-asyncio` for unit tests; `httpx.AsyncClient` against
the FastAPI app (ASGI transport, no real network) for API/contract tests; a real ephemeral
PostgreSQL instance (via `testcontainers-python` or a CI-provided Postgres service container,
never SQLite) for integration tests, since RLS policies and Postgres-specific behavior must be
tested against real Postgres. Frontend — `Vitest` + `React Testing Library` for unit/component
tests, `Playwright Test` (the Playwright *test runner*, distinct from the product's own
Playwright-powered execution engine) for end-to-end tests of the TestPilot dashboard itself.

**Rationale**: Matches the constitution's Test-First and Integration Testing principles directly
— contract tests at the API boundary, integration tests at the DB/queue boundary, using real
Postgres so RLS and constraint behavior (DATA-001, SEC-011) are actually exercised rather than
approximated by SQLite. Using Playwright Test to test *our own frontend* is a deliberate, clearly
documented naming distinction from the product's execution engine to avoid confusing the two in
implementation and in `tasks.md`.

**Alternatives considered**: SQLite for backend integration tests (rejected — cannot validate
Postgres RLS policies, JSONB, or array/GIN-index behavior that the schema relies on); Cypress for
frontend E2E (rejected — Playwright Test is already a project dependency for the automation
engine's ecosystem familiarity and has equivalent capability).

## 15. CI/CD pipeline shape

**Decision**: GitHub Actions with three job stages: (1) lint + type-check + unit tests
(fast, runs on every push), (2) integration/contract tests against ephemeral Postgres+Redis
service containers (runs on every push), (3) build & push versioned Docker images for
api/worker/frontend on merge to `main`. Deployment (staging/prod promotion) is a documented
follow-on step, not implemented as part of this plan.

**Rationale**: Matches constitution's "All code MUST pass automated tests and linting before
being considered complete" and the spec's CI/CD-readiness requirement, staged so fast feedback
(lint/unit) doesn't wait on slower integration tests.

**Alternatives considered**: A single monolithic CI job (rejected — slower feedback loop, no
material simplicity gain); a different CI provider (GitLab CI, CircleCI) (no technical blocker
either way; GitHub Actions chosen as the default with no stated preference against it).

## 16. Containerization & Kubernetes readiness

**Decision**: Three independently deployable container images sharing the backend Python
package as their base: `api` (Uvicorn/Gunicorn serving FastAPI), `worker` (RQ worker process,
same codebase, different entrypoint/CMD), and `frontend` (Next.js production server). Local
development uses `docker-compose` (postgres, redis, minio, api, worker, frontend). Kubernetes
manifests (Deployments, Services, Ingress, ConfigMap/Secret, HPA) are structurally planned
(documented shape, one Deployment per image, liveness/readiness probes wired to the health
endpoints from NFR-010/FR-137) but are a Future implementation task, not produced by this plan.

**Rationale**: Matches NFR-005 (workers scale independently of the API) and the spec's explicit
Kubernetes-readiness requirement, while not implementing infrastructure that isn't part of the
current planning phase (this command explicitly excludes writing implementation artifacts).

**Alternatives considered**: A single combined image running both API and worker processes
(rejected — prevents independently scaling worker replica count from API replica count, directly
contradicting NFR-005).

---

## Summary of Resolved Unknowns

| Area | Decision |
|---|---|
| ORM/migrations | SQLModel + Alembic + asyncpg |
| Auth | Email/password, Argon2id, JWT access + revocable refresh cookie |
| Tenancy enforcement | App-layer scoping dependency + Postgres RLS (defense in depth) |
| Queue/workers | Redis + RQ, 3 logical queues |
| Browser automation | Playwright (Python), context-per-test-case in worker processes |
| AI integration | Internal `LLMProvider` Protocol, adapter selected via config |
| Object storage | S3-compatible via `ArtifactStorage` interface (MinIO locally) |
| Frontend framework | Next.js App Router + TypeScript + Tailwind + Radix primitives |
| Frontend state | TanStack Query only; no global client-state library at MVP |
| Live run status | Polling (MVP) → WebSocket/SSE (Future) |
| Rate limiting | `slowapi` (Redis-backed) |
| Observability | stdlib JSON logging + Prometheus metrics + Sentry |
| Testing | pytest+httpx+real Postgres (backend), Vitest+RTL+Playwright Test (frontend) |
| CI/CD | GitHub Actions, staged (lint/unit → integration → build/push) |
| Containers | 3 images (api/worker/frontend), docker-compose locally, K8s-shaped for later |

No unresolved `NEEDS CLARIFICATION` markers remain.
