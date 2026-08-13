# Implementation Plan: TestPilot AI — AI-Powered Web Application Testing Platform

**Branch**: `001-testpilot-ai-platform` | **Date**: 2026-08-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-testpilot-ai-platform/spec.md`, plus explicit
architecture direction from the `/speckit-plan` invocation (30 named architecture areas, full
frontend/UI/UX scope, and a mandate to verify constitution compliance before finalizing).

**Research**: [research.md](./research.md) — Phase 0, all technical unknowns resolved.

## Summary

TestPilot AI is delivered as a three-deployable monorepo: a **Next.js/TypeScript** dashboard, a
**FastAPI** backend structured as a set of independently testable internal libraries (one per
domain — auth, orgs, projects, test cases, AI generation, AI analysis, execution, issues,
reports, notifications, billing), and a **worker** process (same backend codebase, different
entrypoint) that consumes a Redis-backed job queue to run Playwright-driven browser tests and AI
operations out of the request/response path. PostgreSQL (via SQLModel + Alembic) is the system
of record, with S3-compatible object storage for screenshots/artifacts. Every tenant-owned table
is scoped by `organization_id`, enforced both in application code and via Postgres Row-Level
Security. AI (LLM) access and browser automation are both implemented behind small internal
provider interfaces so either can be swapped without touching calling code. The plan sequences a
practical MVP (unauthenticated-flow testing, single-member Organizations, cloud-LLM-only) while
leaving explicit, non-speculative extension points for every Future Scope item in the spec.

## Technical Context

**Language/Version**: Python 3.12 (backend/worker/CLI), TypeScript 5.x / Node.js 20 LTS
(frontend)

**Primary Dependencies**: FastAPI, SQLModel (SQLAlchemy 2.0 async + `asyncpg`), Alembic, RQ
(Redis Queue), Playwright (Python), `boto3` (S3-compatible storage client), `passlib`+
`argon2-cffi`, `pydantic-settings`, `slowapi`; Next.js (App Router) + TypeScript, Tailwind CSS,
Radix UI primitives, TanStack Query

**Storage**: PostgreSQL 16 (system of record), Redis 7 (job queue + rate-limit counters +
cache), S3-compatible object storage (screenshots/logs; MinIO locally)

**Testing**: pytest + pytest-asyncio + httpx (backend unit/API/contract), real ephemeral
PostgreSQL + Redis via CI service containers or `testcontainers-python` (backend integration);
Vitest + React Testing Library (frontend unit/component), Playwright Test (frontend E2E — the
dashboard's own test suite, distinct from the product's Playwright-powered execution engine)

**Target Platform**: Linux containers; API and worker run as separate Docker images deployable
to Kubernetes; frontend runs as a Next.js Node.js server image

**Project Type**: Web application (frontend + backend + background worker) — Option 2 (web) from
the project-structure template, extended with a third `worker` deployable that shares the
backend codebase

**Performance Goals**: Dashboard/report primary content in <2s (NFR-001, SC-006); test-run
trigger acknowledged in <1s (NFR-002); report aggregation in <3s over a year of history
(NFR-003); AI failure analysis available in <60s for 95% of requests (SC-004)

**Constraints**: Test execution and AI calls MUST run in background workers, never inline in an
API request (NFR-004); every tenant table MUST be `organization_id`-scoped with no query path
that omits it (DATA-001, SEC-011); AI provider and browser-automation engine MUST be replaceable
without changing calling code (NFR-018, NFR-019, INT-002); MVP MUST NOT store site-under-test
credentials (SEC-005)

**Scale/Scope**: MVP targets dozens-to-low-hundreds of Organizations, each with tens of projects
and hundreds of test cases; architecture must reach ≥50 concurrent test runs across tenants once
parallel execution (Future Scope, FR-076) is enabled, without redesign (SC-008)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design below.*

The project constitution (`.specify/memory/constitution.md`, v1.0.0) was written in
library/CLI-tool vocabulary. TestPilot AI is a web SaaS product, so each principle is applied by
substance rather than by surface form. This mapping is stated explicitly here — once — rather
than re-justified per component throughout the plan.

| Principle | How this plan satisfies it |
|---|---|
| **I. Library-First** | The backend is not one monolithic FastAPI app with logic in route handlers. It is a set of independent, independently-testable Python packages under `backend/src/testpilot/` — `auth`, `orgs`, `projects`, `testcases`, `ai_generation`, `ai_analysis`, `ai_provider`, `execution`, `issues`, `reports`, `notifications`, `billing`, `storage`, `audit` — each with its own purpose, its own unit tests, and no dependency on the web framework to be usable. The FastAPI `api/` layer and the `worker/` layer are both thin callers of these libraries, not the libraries' home. |
| **II. CLI Interface** | Each backend library is exposed through a Typer-based CLI (`backend/src/testpilot/cli/`), supporting both human-readable and `--json` output, per library (e.g. `testpilot-cli projects list --json`, `testpilot-cli run execute <run_id>`, `testpilot-cli ai generate-tests <project_id>`). This is a real, load-bearing interface — it is how operators debug, script, and run one-off admin tasks — not a token wrapper added only to satisfy the checklist. |
| **III. Test-First (NON-NEGOTIABLE)** | The Testing Strategy section below and every task generated from this plan in `/speckit-tasks` MUST follow red-green-refactor: failing test committed/reviewed before implementation. This is enforced procedurally in `tasks.md` sequencing, not just stated as intent. |
| **IV. Integration Testing** | Every inter-boundary surface identified in this plan — API endpoints (contract tests against `contracts/`), worker job payload schemas, the `LLMProvider` interface, the `BrowserAutomationEngine` interface, and the Postgres RLS policies — has a corresponding integration/contract test category in the Testing Strategy section. These are exactly the "new library contract surfaces" and "shared schemas" the principle calls out. |
| **V. Observability & Simplicity** | Structured JSON logging and `/metrics`/health endpoints are MVP-required (not deferred), per the Observability section. Simplicity is enforced by explicit rejections in `research.md` of heavier tools (Celery over RQ, WebSockets over polling, a global state store over TanStack Query, a tags table over a `text[]` column) until a concrete, current requirement demands them — each rejection is documented with its reasoning, not asserted. |

**Technology & Quality Constraints** (constitution): CI (below) runs lint + type-check + tests on
every push, so nothing "considered complete" skips that gate. Every dependency introduced in
`research.md` is tied to a specific spec requirement it satisfies — none are speculative.

**Result (pre-design gate)**: PASS. No principle is violated; no Complexity Tracking entries are
required (see bottom of this document).

**Post-Phase-1 re-check**: re-evaluated after `data-model.md`, `contracts/`, and `quickstart.md`
were generated. Nothing in Phase 1 introduced a new dependency, a new deployable, or logic
outside the library boundaries established above — `data-model.md`'s tables map 1:1 onto the
libraries that own them, `contracts/` documents boundaries the Constitution Check already
accounted for (API surface, worker jobs, the two provider interfaces), and `quickstart.md`
introduces no new component, only validation steps against what's already documented. **Result:
PASS, unchanged.**

## Project Structure

### Documentation (this feature)

```text
specs/001-testpilot-ai-platform/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output — all technical decisions
├── data-model.md        # Phase 1 output — entities, fields, relationships, indexes
├── quickstart.md        # Phase 1 output — local dev + end-to-end validation guide
├── contracts/           # Phase 1 output — API and internal interface contracts
│   ├── auth-api.md
│   ├── organizations-api.md
│   ├── projects-api.md
│   ├── test-cases-api.md
│   ├── test-runs-api.md
│   ├── ai-analysis-api.md
│   ├── issues-api.md
│   ├── reports-api.md
│   ├── notifications-api.md
│   ├── billing-api.md
│   ├── worker-jobs.md              # internal queue job payload contracts
│   ├── ai-provider-adapter.md      # internal LLMProvider interface contract
│   └── browser-automation-adapter.md  # internal BrowserAutomationEngine contract
└── checklists/
    └── requirements.md  # Spec quality checklist (from /speckit-specify)
```

### Source Code (repository root)

**Structure Decision**: Web application (Option 2), extended with a third deployable
(`worker/`) that reuses the backend package rather than duplicating logic, plus an `infra/`
directory for container/orchestration definitions. This keeps deployables independently
scalable (NFR-005) while keeping domain logic in one place per the Library-First principle.

```text
testpilot-ai/
├── backend/
│   ├── pyproject.toml
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── src/
│   │   └── testpilot/
│   │       ├── core/                 # config, db session/engine, security primitives,
│   │       │                         # base SQLModel classes, shared exceptions, RLS session setup
│   │       ├── auth/                 # users, password hashing, sessions/refresh tokens,
│   │       │                         # password reset — library
│   │       ├── orgs/                 # organizations, memberships, roles — library
│   │       ├── projects/             # projects CRUD, URL validation/SSRF guard, settings — library
│   │       ├── testcases/            # test case + test step CRUD, search/filter/tag — library
│   │       ├── ai_provider/          # LLMProvider Protocol + concrete adapters — library
│   │       ├── ai_generation/        # orchestrates ai_provider + testcases for FR-036–FR-047
│   │       ├── ai_analysis/          # orchestrates ai_provider + execution results for FR-079–FR-086
│   │       ├── execution/            # BrowserAutomationEngine (Playwright) + test run orchestration
│   │       ├── issues/               # bug/issue tracking — library
│   │       ├── reports/              # aggregation/analytics queries — library
│   │       ├── notifications/        # notification creation + read-state — library
│   │       ├── billing/              # subscription plans + usage tracking/enforcement — library
│   │       ├── storage/              # ArtifactStorage interface + S3/MinIO adapter — library
│   │       ├── audit/                # audit log writer/reader — library
│   │       ├── api/                  # FastAPI app: thin HTTP layer over the libraries above
│   │       │   ├── main.py            # app factory, middleware (correlation ID, CORS, RLS session)
│   │       │   ├── deps.py            # current_user, current_org, rate-limit deps
│   │       │   └── v1/
│   │       │       ├── auth.py
│   │       │       ├── organizations.py
│   │       │       ├── projects.py
│   │       │       ├── testcases.py
│   │       │       ├── testruns.py
│   │       │       ├── issues.py
│   │       │       ├── reports.py
│   │       │       ├── notifications.py
│   │       │       ├── billing.py
│   │       │       └── health.py
│   │       ├── worker/               # RQ worker entrypoints; each queue -> one job module
│   │       │   ├── main.py
│   │       │   └── jobs/
│   │       │       ├── generate_test_cases.py
│   │       │       ├── execute_test_run.py
│   │       │       └── analyze_failure.py
│   │       └── cli/                  # Typer CLI wiring every library to a command (Principle II)
│   │           └── main.py
│   └── tests/
│       ├── unit/          # per-library unit tests (no DB/network)
│       ├── integration/   # real Postgres + Redis, RLS policy tests, worker job tests
│       └── contract/      # httpx ASGI tests against contracts/*.md
├── frontend/
│   ├── package.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── src/
│   │   ├── app/                      # Next.js App Router — see Frontend Architecture below
│   │   ├── components/               # design-system primitives + shared composites
│   │   ├── features/                 # feature-scoped modules (projects, testcases, testruns,
│   │   │                             # issues, reports, assistant, billing, notifications)
│   │   ├── lib/                      # typed API client, auth/session helpers, query client,
│   │   │                             # theme provider
│   │   └── styles/                   # Tailwind base layer, design tokens (CSS variables)
│   └── tests/
│       ├── unit/           # Vitest + RTL
│       └── e2e/            # Playwright Test (dashboard E2E, not the product engine)
├── infra/
│   ├── docker/
│   │   ├── backend.Dockerfile        # shared base; CMD overridden for api vs worker
│   │   ├── frontend.Dockerfile
│   │   └── docker-compose.yml        # postgres, redis, minio, api, worker, frontend
│   └── k8s/                          # documented shape only — see Kubernetes-Readiness below
│       ├── base/
│       └── overlays/
├── .github/
│   └── workflows/
│       └── ci.yml
├── specs/
└── .specify/
```

---

## System Architecture Overview

```
                         ┌─────────────────────────┐
                         │   Next.js Frontend       │
                         │   (dashboard + landing)  │
                         └────────────┬─────────────┘
                                      │ HTTPS / JSON (TanStack Query)
                                      ▼
                         ┌─────────────────────────┐        ┌──────────────┐
                         │   FastAPI API layer      │──────▶│  PostgreSQL   │
                         │  (auth, orgs, projects,  │        │ (RLS-scoped)  │
                         │  testcases, issues, ...) │◀──────│               │
                         └────────────┬─────────────┘        └──────────────┘
                                      │ enqueue job                 ▲
                                      ▼                             │ read/write
                         ┌─────────────────────────┐                │
                         │   Redis (queue + rate    │                │
                         │   limits + cache)         │                │
                         └────────────┬─────────────┘                │
                                      │ dequeue                      │
                                      ▼                               │
                         ┌─────────────────────────┐                │
                         │   Worker processes        │────────────────┘
                         │  ┌───────────────────┐   │
                         │  │ execution (Playwright)│─────▶ target website (public URL)
                         │  ├───────────────────┤   │
                         │  │ ai_generation /     │───────▶ LLMProvider adapter ──▶ Cloud LLM API
                         │  │ ai_analysis         │   │
                         │  └───────────────────┘   │
                         └────────────┬─────────────┘
                                      │ artifacts (screenshots/logs)
                                      ▼
                         ┌─────────────────────────┐
                         │  S3-compatible storage    │
                         └─────────────────────────┘
```

**Communication summary**:
- Frontend ↔ API: synchronous HTTPS/JSON, authenticated via httpOnly refresh cookie + short-lived
  JWT access token; TanStack Query polls in-flight test-run/AI-job status (Research #11).
- API ↔ Postgres: async SQLAlchemy (via SQLModel) session per request; every session sets the
  RLS org context for the request's Organization before any query runs.
- API ↔ Redis: enqueues job payloads (Research #5) for generation, execution, and analysis;
  also used for rate-limit counters (SEC-009) and cache (NFR-008).
- Worker ↔ Redis/Postgres/Storage: dequeues a job, executes it (Playwright run or AI call),
  writes results to Postgres, uploads artifacts to object storage, enqueues a notification.
- Worker ↔ AI provider: exclusively through the `LLMProvider` interface — no direct SDK calls
  from `execution`, `api`, or any other module (Research #7).
- Worker ↔ target website: exclusively through the `BrowserAutomationEngine` (Playwright)
  interface, after the SSRF/private-address check (FR-035/FR-135) has passed at project-creation
  and re-validated at execution time.

---

## Frontend Architecture (Next.js + TypeScript + Tailwind)

### Route map (Next.js App Router)

Route groups separate layouts that must not leak into each other (public marketing vs. bare
auth vs. authenticated dashboard shell):

```text
app/
├── (marketing)/                       # public, unauthenticated, SEO-relevant
│   ├── layout.tsx                     # marketing nav + footer, no sidebar
│   ├── page.tsx                       # "/" — Landing page
│   └── pricing/page.tsx               # plan tiers overview (maps to billing FRs)
│
├── (auth)/                            # public, unauthenticated, centered card layout
│   ├── layout.tsx
│   ├── login/page.tsx
│   ├── signup/page.tsx
│   ├── forgot-password/page.tsx
│   └── reset-password/page.tsx        # ?token=... from email link
│
└── (dashboard)/                       # authenticated shell: sidebar + topbar + content
    ├── layout.tsx                     # auth guard, org context, sidebar nav (FR-020)
    ├── overview/page.tsx              # Overview (FR-021)
    ├── projects/
    │   ├── page.tsx                   # Projects list (FR-033)
    │   ├── new/page.tsx               # Create project (FR-025)
    │   └── [projectId]/
    │       ├── page.tsx               # Project detail + testing history (FR-030)
    │       ├── settings/page.tsx      # Edit/archive/delete (FR-027–FR-029, FR-031)
    │       ├── test-cases/
    │       │   ├── page.tsx           # Library: search/filter/sort (FR-049–FR-052)
    │       │   ├── new/page.tsx       # Manual test case (FR-053)
    │       │   ├── generate/page.tsx  # AI generation trigger + review queue (FR-036–FR-044)
    │       │   └── [testCaseId]/page.tsx  # Edit / approve / reject / regenerate
    │       ├── test-runs/
    │       │   ├── page.tsx           # Run history (FR-076)
    │       │   ├── new/page.tsx       # Select cases → start run (FR-069)
    │       │   └── [testRunId]/
    │       │       ├── page.tsx       # Live run monitor (FR-071)
    │       │       └── results/[testResultId]/page.tsx  # Log + screenshots + AI analysis panel
    │       ├── issues/
    │       │   ├── page.tsx           # Project issue list (FR-093)
    │       │   ├── new/page.tsx       # Manual issue (FR-088)
    │       │   └── [issueId]/page.tsx # Issue detail (FR-089–FR-092, FR-095)
    │       └── reports/page.tsx       # Project report/analytics (FR-104–FR-110)
    ├── assistant/page.tsx             # AI QA Assistant chat — Future (FR-097–FR-103), scaffolded
    ├── settings/
    │   ├── profile/page.tsx           # Name/email/password (FR-006)
    │   ├── security/page.tsx          # Active sessions, logout-everywhere (FR-008)
    │   ├── organization/page.tsx      # Workspace name, org-level settings (FR-013)
    │   ├── members/page.tsx           # Invites/roles — Future (FR-016–FR-019), scaffolded
    │   └── billing/page.tsx           # Plan, usage vs. limits (FR-119, FR-125)
    └── notifications/page.tsx         # Full notification history; a topbar bell opens a
                                        # slide-over using the same data for quick access (FR-117)
```

Every `[projectId]` segment loads project context (name, URL, status) once in a layout-level
loader and makes it available to all nested pages, satisfying FR-024 without re-fetching per
page.

### Primary user flows mapped to routes

1. **Sign up → first test run** (Story 1–5): `/signup` → `/overview` (empty state) →
   `/projects/new` → `/projects/[id]` → `/projects/[id]/test-cases/generate` → review/approve →
   `/projects/[id]/test-runs/new` → `/projects/[id]/test-runs/[id]` (live monitor) →
   `/projects/[id]/test-runs/[id]/results/[id]` (AI analysis on any failure).
2. **Triage a failure into a bug** (Story 5–7): from a result detail page, "Create Issue" opens
   pre-filled at `/projects/[id]/issues/new?fromResult=[id]`, lands on
   `/projects/[id]/issues/[id]` after save.
3. **Weekly quality check** (Story 8): `/projects/[id]/reports` for a single project;
   Organization-level rollup is a Future addition to `/overview`, not a new route (FR-113).
4. **Respond to a notification** (Story 9): topbar bell slide-over → click → deep-links directly
   into the relevant run/result/issue route.

### Design system

- **Tokens**: color, spacing, radius, and typography scales defined as CSS custom properties in
  `src/styles/tokens.css`, consumed by `tailwind.config.ts` (`theme.extend` reads the variables)
  so Tailwind utility classes and raw CSS stay on one source of truth.
- **Color semantics** (UX-003): status colors (passed/failed/skipped/running/queued) and
  severity colors (minor/major/critical/blocker) are named tokens (`--status-passed`,
  `--severity-critical`, …), never inlined hex values in components — this is what makes theme
  switching and colorblind-safe pairing (color + icon/text, never color alone) enforceable in
  one place.
- **Typography**: one variable font family, a small fixed type scale (display/heading/body/
  caption/mono-for-logs), no ad hoc font sizes in feature code.
- **Component layer** (`src/components/`): built on unstyled Radix UI primitives
  (Dialog, DropdownMenu, Tabs, Tooltip, Toast, Popover) styled with Tailwind, in a
  shadcn/ui-style local-ownership pattern (components live in-repo, not consumed as an opaque
  npm package) so they can be adapted to TestPilot's visual language without fighting a
  third-party API.

### Component inventory (shared, `src/components/`)

- **Layout**: `SidebarNav`, `Topbar`, `PageHeader`, `EmptyState`, `ErrorState`, `LoadingState`
  (skeletons, not spinners, for content-shaped loading per UX-005).
- **Data display**: `DataTable` (sort/filter/search built in, used by test cases/runs/issues —
  UX-008), `StatusBadge`, `SeverityBadge`, `PriorityBadge` (icon + text + color — UX-003),
  `Card`, `StatCard` (Overview metrics), `Timeline` (execution log), `ScreenshotViewer`
  (lightbox with keyboard navigation).
- **Feedback**: `Toast` (transient success/error — UX-006), `ProgressBar` /
  `RunProgressRing` (live test-run completion — UX-004), `ConfirmDialog` (destructive actions:
  archive/delete per FR-029).
- **Forms**: `TextField`, `Select`, `TagInput`, `URLField` (client-side well-formedness check
  mirroring FR-026 before submit), `TestStepEditor` (structured step builder for manual/edited
  test cases), all built on native `<form>` + Radix primitives, not a heavy form framework beyond
  a thin schema-validation layer (see Error Handling below).
- **Charts** (Reports): thin wrappers around a lightweight charting library (e.g. Recharts) for
  pass-rate trend, severity distribution, and coverage — chart components accept plain-QA-term
  labels as props (UX-009), no chart owns its own data-fetching.

### States (every primary view implements all four — UX-005)

| State | Pattern |
|---|---|
| **Loading** | Skeleton components shaped like the eventual content (table-row skeletons, card skeletons), never a bare spinner for content-bearing views |
| **Empty** | Illustration/icon + one-sentence explanation + a primary action (e.g., Projects empty state's action is "Create your first project") — never a blank table |
| **Error** | Distinct from empty: explicit "Something went wrong" + retry action; AI-specific error states (generation/analysis unavailable) get their own copy distinguishing "AI failed" from "no failures yet" per the spec's edge cases |
| **Success** | Toasts for transient confirmations (save, approve, run started); persistent success is just the updated view itself (e.g., a completed run simply shows its results — no modal) |

### Responsive layout strategy (NFR-015)

- Breakpoints: mobile (<640px), tablet (640–1024px), desktop (>1024px), Tailwind's default
  scale, no custom breakpoints unless a specific view needs one.
- Sidebar collapses to a slide-over drawer below the tablet breakpoint; the topbar gains a menu
  toggle.
- `DataTable`-based views (test cases, test runs, issues) switch to a stacked card layout on
  mobile — dense tables are a desktop/tablet pattern per NFR-015's "primary flows fully
  functional on mobile" (not "identical layout on mobile").
- Charts on Reports reflow to a single column and reduce to their top-line stat + one primary
  chart on mobile, with the rest reachable by scroll — not hidden.

### Dark/light theme architecture (UX-007)

- Theme is driven entirely by CSS custom properties (the same tokens above) swapped via a
  `data-theme="light"|"dark"` attribute on `<html>`, plus `prefers-color-scheme` as the default
  before a user override is chosen.
- A `ThemeProvider` in `src/lib/` persists the user's choice (local storage at MVP; a
  per-user server-side preference is a natural Future addition to the `users` table, not a
  redesign).
- Because components consume tokens (never raw colors), adding/adjusting the dark palette is a
  token-file change, not a per-component rewrite — this is the concrete mechanism behind "no
  rebuild of individual screens to add the second theme," per NFR/UX-007's requirement.

### Accessibility strategy (NFR-013, NFR-014)

- All interactive primitives come from Radix, which provides correct ARIA roles, focus trapping
  (dialogs), and keyboard interaction patterns (menus, tabs) out of the box — this is the
  primary mechanism for meeting WCAG 2.1 AA interaction expectations without hand-rolling it.
- Every icon-only control has an accessible name (`aria-label`); status/severity/priority badges
  always pair color with text or an icon, never color alone (UX-003/NFR-014).
- Focus order follows visual/DOM order; route transitions move focus to the new page's `<h1>` so
  keyboard/screen-reader users aren't stranded on the previous page's last focused element.
- Color tokens are chosen to meet 4.5:1 contrast for body text and 3:1 for large text/UI
  components in both themes; this is a token-authoring constraint, verified in the frontend
  testing strategy below.
- Automated accessibility linting (`eslint-plugin-jsx-a11y`) runs in CI; it catches missing
  labels/roles but does not replace manual keyboard-only pass-throughs of the primary flows
  before release.

### Frontend state & data fetching (Research #10, #11)

- All server data goes through TanStack Query; query keys are namespaced by Organization and
  entity (`['org', orgId, 'projects']`, `['project', projectId, 'testcases']`, …) so
  cache invalidation after a mutation (e.g., approving a test case) is precise, not a blunt
  refetch-everything.
- In-flight test runs and pending AI generation/analysis jobs use `refetchInterval` polling that
  stops automatically once the resource reaches a terminal state — no manual polling loops in
  component code.
- No global client-state store; component-local `useState`/`useReducer` covers UI-only state
  (open panels, form drafts before submit, active table filters held in the URL query string so
  filtered views are shareable/bookmarkable, matching UX-008's "in-context" expectation).

---

## Backend Architecture (FastAPI + SQLModel + PostgreSQL)

### Responsibility split

- **`api/` layer**: HTTP concerns only — request parsing/validation (via SQLModel/Pydantic
  schemas), auth/rate-limit dependency injection, calling into the relevant library, and
  translating library-level results/exceptions into HTTP responses. No business logic lives
  here.
- **Domain libraries** (`auth/`, `orgs/`, `projects/`, `testcases/`, `issues/`, `reports/`,
  `notifications/`, `billing/`, `audit/`): own their entities, validation rules, and business
  operations; each is importable and testable without FastAPI running.
- **`ai_provider/`, `ai_generation/`, `ai_analysis/`**: `ai_provider` owns only the
  provider-agnostic interface and adapters; `ai_generation`/`ai_analysis` own the orchestration
  (prompt construction from project/test data, persistence of results) and are the only callers
  of `ai_provider`.
- **`execution/`**: owns `BrowserAutomationEngine` (Playwright adapter), test run orchestration
  (selecting cases, sequencing execution, recording results), and the SSRF/private-address guard
  re-checked at execution time.
- **`storage/`**: owns the `ArtifactStorage` interface; all screenshot/log persistence goes
  through it — no direct `boto3` calls outside this module.
- **`worker/`**: thin job handlers that call exactly one orchestration entrypoint each
  (`ai_generation.generate_for_project(...)`, `execution.run_test_run(...)`,
  `ai_analysis.analyze_result(...)`) and handle job-level retry/timeout/error-state transitions
  (FR-046, FR-083).
- **`cli/`**: Typer commands that call the same library entrypoints the API and worker call —
  no logic is duplicated for the CLI's sake.

### Dependency flow (one-directional, enforced by import discipline / lint rule)

```
api, worker, cli
   │
   ▼
ai_generation, ai_analysis, execution, reports, notifications, billing
   │
   ▼
auth, orgs, projects, testcases, issues, ai_provider, storage, audit
   │
   ▼
core  (config, db session, base models, exceptions, RLS context)
```

Lower layers never import from higher layers (e.g., `core` never imports `projects`); this keeps
each library genuinely standalone per the Library-First principle and makes unit-testing a
library possible without booting the whole app.

### Request lifecycle (typical authenticated write, e.g. "create project")

1. `api/deps.py` resolves `current_user` from the access-token cookie/header, then
   `current_organization` from the user's membership.
2. A DB session is opened; `SET LOCAL app.current_org_id` is issued so RLS is active for the
   rest of the transaction (Research #4).
3. The route calls `projects.create_project(session, org_id, payload)`; the library validates
   the URL (well-formedness + SSRF/private-range rejection, FR-026/FR-035) before insert.
3. On success, the route returns the created resource; on a library-raised domain exception
   (e.g., `PlanLimitExceeded`), a shared exception handler maps it to the correct HTTP status
   and a structured error body (see Error Handling below) — routes don't hand-translate errors
   themselves.

### Async job lifecycle (e.g., "generate test cases")

1. Route validates the request, checks the Organization's AI-operation usage against its plan
   limit (`billing.check_and_reserve_usage(...)`), and enqueues a `GenerateTestCasesJob` onto
   the `ai-generation` Redis queue (contract in `contracts/worker-jobs.md`) with a
   `generation_run_id` the client can poll.
2. A worker dequeues the job, calls `ai_generation.generate_for_project(...)`, which fetches the
   project's public pages (a lightweight crawl/analysis step within `ai_generation`), builds a
   prompt, calls `ai_provider.generate_test_cases(...)`, persists resulting `TestCase`/
   `TestStep` rows with `status=draft`, and marks the generation run `completed` (or `failed`
   with a reason, per FR-046).
3. The worker enqueues a `notifications.create(...)` call (or writes the notification directly —
   notification writes are cheap enough not to need their own queue) so the initiating user is
   notified per FR-116.
4. The frontend, which has been polling the generation run's status, sees `completed` and
   fetches the new draft test cases for review.

The same three-step shape (validate+enqueue → worker executes+persists → notify) is used for
test execution and AI failure analysis, which is why `worker-jobs.md` documents all three job
payloads with one consistent envelope (job id, organization_id, requested_by, resource id,
timestamps) rather than three unrelated shapes.

---

## Authentication, Authorization & Multi-Tenant Architecture

Covered in depth in `research.md` (#3, #4) and `contracts/auth-api.md`. Summary of the
architecture, not a restatement of the research rationale:

- **Identity**: `users` table, Argon2id-hashed passwords, email uniqueness enforced at the DB
  level (`citext` + unique index).
- **Session**: JWT access token (15 min, signed with a backend-only secret from
  `pydantic-settings`) + a `refresh_tokens` table (hashed token, expiry, revoked_at) delivered as
  an httpOnly cookie. Logout revokes the specific refresh token; "log out everywhere"
  (Settings → Security) revokes all of a user's refresh tokens.
- **Tenancy**: `organizations` is the tenant root. `memberships` joins `users` and
  `organizations` with a `role` (owner/admin/member — only `owner` is ever populated at MVP
  signup per the personal-Organization decision, FR-012–FR-015). Every tenant-owned table
  carries `organization_id`.
- **Authorization**: two layers — (1) a FastAPI dependency requires `current_organization` and
  passes it explicitly into every library call (no implicit global org context); (2) Postgres
  RLS policies on every tenant table (`USING (organization_id = current_setting('app.current_org_id')::uuid)`)
  so a bug that forgets (1) still cannot cross tenants. FR-138/SEC-011's "fail closed, indistinguishable
  from not-found" is implemented by having the ORM layer return "not found" for any row RLS
  hides — the API layer cannot even observe the difference between "doesn't exist" and "exists
  in another org," so it cannot leak it.
- **Future roles/permissions** (FR-016–FR-019): the `role` enum and `memberships` table already
  support `admin`/`member`; only the invite flow and permission-gating middleware are Future
  work — no schema change needed later.

---

## AI Test-Case Generation Architecture

- **Input**: project URL + any generation preferences from `projects.settings`.
- **Analysis step** (`ai_generation`): a lightweight same-worker crawl of the target site's
  publicly reachable pages (bounded page count and depth to keep generation time bounded, per
  NFR/latency expectations) using the same `BrowserAutomationEngine` interface `execution` uses
  — reused, not duplicated, since both need "load a page and read its DOM."
- **Prompt construction**: structured extraction (page titles, forms, links, interactive
  elements) is turned into a bounded, token-budgeted prompt — raw HTML is not sent wholesale to
  the LLM.
- **Generation call**: `ai_provider.generate_test_cases(context) -> list[GeneratedTestCase]`,
  a structured (JSON-schema-validated) response, not free-text parsing — the adapter is
  responsible for getting structured output from its underlying provider (e.g., via tool-use/
  function-calling or a JSON response mode), so `ai_generation` never regex-parses prose.
- **Persistence**: results are written as `TestCase`/`TestStep` rows with `status=draft`,
  `source=ai_generated`, exactly as returned — no silent mutation before user review (DATA-006).
- **Review loop**: edit/approve/reject/regenerate are plain CRUD + a re-invocation of the same
  generation call scoped to one case or the whole batch (FR-043).
- **Concurrency guard**: a per-project advisory lock (or a `generation_status` row checked before
  enqueueing) prevents two concurrent generation jobs for the same project (FR-047).
- **Security**: only data already scoped to the requesting Organization's project is included in
  the prompt (SEC-012); the target site is fetched only after the SSRF guard passes.
- **Testing**: `ai_provider` adapters are tested against a fake/mock provider implementing the
  same Protocol in unit tests; one contract test per adapter verifies it satisfies the Protocol's
  structured-output guarantee against a real (sandboxed/low-cost) provider call in CI, gated to
  run less frequently than the full suite if latency/cost requires it.

## AI Failure-Analysis Architecture

- **Input assembly** (`ai_analysis`): pulls the failing `TestStep`, its expected assertion, the
  actual observed state/error captured during execution, the relevant log excerpt, and the
  failure screenshot's storage reference from `TestResult`/`Artifact` (FR-080).
- **Generation call**: `ai_provider.analyze_failure(context) -> FailureAnalysis` (explanation,
  root cause, severity, suggested fix — FR-081), again structured output, not free text.
- **Persistence & versioning**: each analysis request creates a new `AIAnalysis` row linked to
  the `TestResult` (not an update-in-place), so re-requesting analysis (FR-085) preserves history
  rather than overwriting it.
- **Failure handling**: timeout/error from the provider marks the analysis job `failed` with a
  reason surfaced to the user (FR-083) — never a fabricated placeholder result.
- **Security**: identical Organization-scoping guarantee as generation (SEC-012) — analysis
  requests can only ever read data already belonging to the requester's Organization, enforced by
  the same RLS-backed queries used everywhere else, not a separate bespoke check.

## Browser Automation & Test Execution Architecture

- **`BrowserAutomationEngine` interface** (`execution/engine.py`): `run_test_case(test_case) ->
  TestResult` plus the step-executor primitives (`navigate`, `click`, `type`, `submit`,
  `assert_url`, `assert_content`, `assert_element`) mapped 1:1 to `TestStep.action_type`
  (FR-059–FR-063). The Playwright adapter is the only implementation at MVP; the interface exists
  so a second engine could be added without touching `TestCase`/`TestStep`/`TestResult` models
  (FR-068/NFR-019).
- **Isolation**: one `BrowserContext` per `TestCase` execution, from a pre-warmed per-worker
  `Browser` instance (Research #6) — cookies/storage never leak between test cases in the same
  run (FR-067).
- **Timeouts**: a per-step timeout and an overall per-test-case timeout are enforced by the
  engine itself (not left to the caller), satisfying FR-066 regardless of which orchestrator
  calls it.
- **Fault isolation**: a crashed `BrowserContext`/page is caught at the engine boundary and
  translated into a `TestResult(status=error)` for that one case; the orchestrator in
  `execution/runner.py` continues to the next case in the run (FR-075/NFR-007).
- **Evidence capture**: a screenshot is always taken on failure; additional checkpoint
  screenshots are opt-in per `TestStep` (FR-064). Screenshots and the structured step log are
  handed to `storage.save_artifact(...)` immediately, not batched at run-end, so a crash after a
  partial run doesn't lose already-captured evidence (spec Edge Cases).
- **SSRF guard**: re-validated immediately before navigation (not only at project-creation time),
  since a project's URL could theoretically be edited between creation and execution — this is a
  cheap, mandatory re-check, not redundant defense-in-depth for its own sake.

## Background Jobs & Worker Architecture

- **Queues**: `ai-generation`, `test-execution`, `ai-analysis` (Research #5) — separate so a
  burst of, e.g., test executions cannot delay AI-analysis jobs users are actively waiting on.
- **Worker processes**: one worker deployable (`infra/docker/backend.Dockerfile` with a
  different `CMD`) can be scaled independently per queue via replica count/argument, satisfying
  NFR-005.
- **Job envelope** (`contracts/worker-jobs.md`): every job carries `job_id`, `organization_id`,
  `requested_by_user_id`, a resource reference (project/test-run/test-result id), `enqueued_at`,
  and a `correlation_id` reused from the originating API request for end-to-end log tracing
  (NFR-009).
- **Retry policy**: RQ's built-in retry with exponential backoff, bounded (e.g., 2 retries) for
  transient AI-provider/network failures; a job that exhausts retries transitions its resource to
  an explicit terminal `failed`/`unavailable` state rather than disappearing silently.
- **Idempotency**: job handlers check the current state of their target resource before acting
  (e.g., a generation job for an already-completed generation run is a no-op), so a redelivered
  job (queue-level at-least-once delivery) cannot double-apply.

## Screenshot & Artifact Storage Architecture

- **`ArtifactStorage` interface** (`storage/`): `put(bytes, content_type) -> storage_key`,
  `get_url(storage_key, expires_in) -> signed URL`. Only this module talks to `boto3`.
- **Access pattern**: the frontend never receives a raw storage credential; it receives a
  short-lived signed URL from the API for each artifact it needs to display (SEC-013's "prevent
  serving as executable content" is enforced by setting `Content-Disposition`/content-type
  correctly on generation and by the bucket never allowing public/anonymous read).
- **Retention** (DATA-003): a scheduled worker job (not a request-path operation) purges
  artifacts older than the configured retention window, nulling the `Artifact` row's
  `storage_key` while leaving the parent `TestResult`'s pass/fail outcome intact.

## Reports & Analytics Architecture

- Reports are **computed on read**, not a separately maintained table, for the MVP's data
  volumes — aggregation queries over `test_runs`/`test_results`/`issues` filtered by
  `organization_id` + `project_id` + time range, using the denormalized summary counters on
  `test_runs` (see `data-model.md`) to avoid re-aggregating every `test_result` row for
  frequently-viewed totals.
- Trend data (Future, FR-108) is the one place a small materialized/cached rollup (e.g., a daily
  `project_quality_snapshots` row) is anticipated, but is explicitly **not** built at MVP —
  called out here only so `/speckit-tasks` doesn't need to re-derive this decision later.

## Notifications Architecture

- Notifications are written synchronously by whichever process completes the triggering event
  (the worker, for run-completed/analysis-completed; the API, for nothing at MVP since no
  API-only-triggered notification exists yet) directly into the `notifications` table — no
  separate notification queue at MVP, since a row insert is cheap and doesn't need retry
  semantics the way an external AI/browser call does.
- The frontend polls/queries `notifications` the same way it queries any other resource (TanStack
  Query), with a `read_at` mutation for mark-as-read.
- Delivery-channel abstraction (email/webhook, FR-119) is a Future addition of a `channel` field
  and a delivery worker — the `notifications` table shape already anticipates this via a
  `type` + `related_entity` design that doesn't need to change.

## Bug/Issue Management Architecture

- `issues` library owns creation (both from a `TestResult` and manual), status lifecycle, and
  linkage. "Create from failed result" is a single library call that copies the failure's
  screenshot/log references into `issue_attachments` (by reference, not by re-uploading bytes) so
  the issue keeps its evidence even if the originating `TestResult` is superseded later
  (FR-096).

## Subscription & Usage-Limit Architecture

- `subscription_plans` is a small reference table (Free/Starter/Professional/Enterprise) with
  per-plan limit columns; `organizations.plan_id` points at one row.
- `usage_records` tracks consumption per Organization per billing period per metric
  (projects/test-executions/ai-operations/members); `billing.check_and_reserve_usage(...)` is
  called at the point of action (project creation, run enqueue, generation/analysis enqueue) and
  raises a typed `PlanLimitExceeded` exception the API layer turns into a specific 402/403-style
  response naming the limit (FR-125).
- Already-enqueued work is never retroactively cancelled by a limit change mid-flight (FR-126) —
  the check happens only at the enqueue/creation boundary, never inside a running job.
- No payment gateway integration exists at MVP (FR-129/INT-005); `organizations.plan_id`
  defaults to Free at signup and is otherwise operator-set until a gateway is added.

---

## API Design

Full endpoint-by-endpoint contracts are in `contracts/*.md` (Phase 1). Summary of the
organization:

- REST, versioned under `/api/v1/`, resource-oriented (`/projects`, `/projects/{id}/test-cases`,
  `/projects/{id}/test-runs`, …), JSON request/response bodies validated by SQLModel/Pydantic
  schemas at the boundary (NFR-017).
- Async/long-running operations (generation, execution, analysis) follow a consistent
  "create a job resource, poll its status" shape rather than three bespoke async patterns:
  `POST .../generate` → `202 {generation_run_id, status: "queued"}`; client polls
  `GET .../generate/{generation_run_id}`.
- Errors follow one shared envelope (`{"error": {"code", "message", "details"}}`) so the frontend
  has one error-handling code path (see Error Handling below) instead of one per endpoint.
- `GET /healthz` (liveness) and `GET /readyz` (readiness, checks DB/Redis connectivity) are
  unauthenticated per FR-137/NFR-010.
- `GET /metrics` is Prometheus-format, restricted to internal network access (not exposed via the
  public ingress) per standard practice for metrics endpoints.

## Database Design

Full entity/field/index detail is in `data-model.md` (Phase 1). Architectural notes that shape
that document:

- Every tenant-owned table: `id UUID PK`, `organization_id UUID NOT NULL` (FK + index), standard
  `created_at`/`updated_at` timestamps.
- RLS policy applied uniformly across tenant tables using the same `current_setting('app.current_org_id')`
  pattern — one policy template, not bespoke per-table logic.
- Denormalized counters (`test_runs.summary_*`, `test_cases.last_result`) trade a small amount of
  write-time bookkeeping for read-path speed on the views users check most often (Overview,
  Reports), consistent with NFR-001/NFR-003's latency targets.
- Full-text search for the test case library (FR-050) uses a generated `tsvector` column + GIN
  index rather than a separate search service, appropriate for the MVP's per-project data volume
  (hundreds, not millions, of test cases).

---

## Error Handling & Validation

- **Input validation**: happens once, at the API boundary, via SQLModel/Pydantic request models
  (FR-132/NFR-017); a library function is never called with unvalidated primitive dicts from a
  route — the route's request model is what's passed through.
- **Domain errors**: each library raises typed exceptions (`ProjectNotFound`,
  `PlanLimitExceeded`, `GenerationInProgress`, `InvalidProjectURL`, …) rather than returning
  sentinel values; a single FastAPI exception-handler layer maps exception types to HTTP status
  codes and the shared error envelope, so error-to-status mapping lives in one place, not
  scattered across route handlers.
- **Cross-tenant access**: because RLS makes another Organization's row invisible, "not found"
  and "belongs to another org" are the same code path by construction — there is no separate
  "forbidden" branch to accidentally get wrong (FR-138/SEC-011, reiterated here because it's an
  error-handling property, not just an authz property).
- **Frontend**: TanStack Query's error channel feeds one shared `<ErrorState>` renderer per view,
  parameterized by the error envelope's `code`, so a new backend error code gets a sensible
  default rendering without new frontend code, with specific codes (e.g.,
  `ai_analysis_unavailable`) opted into custom copy where the spec calls for a distinct message
  (edge cases in spec.md).

## Security Architecture

Cross-references the Security Requirements in spec.md; this section states the mechanism, not
the requirement:

- **AuthN/AuthZ**: Section "Authentication, Authorization & Multi-Tenant Architecture" above
  (SEC-001–SEC-003).
- **Secrets**: all secrets (DB URL, JWT signing key, AI provider keys, S3 credentials) loaded via
  `pydantic-settings` from environment variables only; local dev uses a git-ignored `.env`
  (with `.env.example` committed) and production uses platform secret injection (K8s Secrets),
  never baked into an image or committed (SEC-004/FR-133).
- **SSRF prevention**: a shared `validate_public_url()` guard (used at project-creation and
  re-checked at execution time) resolves the URL's DNS and rejects private/loopback/link-local/
  reserved ranges before any HTTP or Playwright navigation is permitted (SEC-006/FR-035/FR-135).
- **Input sanitization / XSS**: React's default escaping handles output encoding for all
  AI-generated and user-authored text rendered in the dashboard; the API additionally validates
  field lengths/shapes on the way in (SEC-007).
- **CSRF**: state-changing requests require the access token (sent as an `Authorization` header
  by the frontend's API client, not solely relied upon via cookie), which is not automatically
  attached by a browser to a cross-site request the way a cookie alone would be; the refresh
  cookie itself is `SameSite=Lax` as a second layer (SEC-008).
- **Rate limiting**: `slowapi` + Redis on auth, AI, and execution-trigger endpoints
  (SEC-009/FR-132).
- **Audit logging**: `audit` library writes an append-only row (no update/delete endpoint exists
  for it, enforced by simply not building one) for auth events, permission changes, and
  deletions (SEC-010/FR-128–FR-129).
- **Artifact safety**: covered in Screenshot & Artifact Storage Architecture above (SEC-013).
- **Dependency hygiene**: CI runs a dependency vulnerability scan (e.g., `pip-audit` /
  `npm audit`) as part of the lint/checks stage, failing the build on high-severity findings.

## Observability

- **Logging**: stdlib `logging` with a JSON formatter; every log line includes
  `correlation_id`, `organization_id` (when available), and `user_id` (when available) — API
  middleware generates/propagates `correlation_id`, worker jobs inherit it from the job envelope
  (NFR-009).
- **Metrics**: `prometheus-fastapi-instrumentator` for API request metrics; custom counters/
  histograms for job queue depth, job duration, and job failure rate per queue (test-execution
  throughput, AI request latency/error rate — NFR-011/FR-138).
- **Health checks**: `/healthz` (process is up) and `/readyz` (DB + Redis reachable) on the API;
  an equivalent liveness check on the worker process (can it reach Redis) for Kubernetes probes
  (NFR-010).
- **Error tracking**: Sentry SDK on both API and worker processes, capturing unhandled
  exceptions with `correlation_id`/`organization_id` tags for fast cross-referencing against logs
  (NFR-012).

## Testing Strategy

Directly implements the constitution's Test-First and Integration Testing principles.

| Layer | Tooling | What it covers | Constitution tie |
|---|---|---|---|
| Backend unit | pytest, no DB/network | Library business logic in isolation (e.g., URL validation, plan-limit math, prompt construction) | Library-First — each library testable alone |
| Backend contract | pytest + httpx ASGI transport | Every endpoint in `contracts/*.md` — request/response shape, status codes, auth/authz enforcement | Integration Testing — API contract surface |
| Backend integration | pytest + real Postgres/Redis (CI service containers) | RLS policies actually deny cross-org reads; queue enqueue→dequeue→persist round trip; migrations apply cleanly | Integration Testing — DB/queue boundaries |
| `LLMProvider` contract | pytest, fake provider + one gated real-provider smoke test | Every adapter satisfies the Protocol's structured-output contract | Integration Testing — swappable-provider boundary |
| `BrowserAutomationEngine` contract | pytest-playwright against a local fixture page | Every action/assertion type behaves per FR-059–FR-064 against a known page | Integration Testing — execution engine boundary |
| Frontend unit | Vitest + React Testing Library | Component rendering, state/empty/error/loading variants, accessibility roles present | — |
| Frontend E2E | Playwright Test | Primary user flows from the Route Map end-to-end against a running stack | Integration Testing — full-stack user journeys |

**Process**: for every task in the eventual `tasks.md`, a failing test is written and reviewed
before the corresponding implementation task begins (constitution Principle III,
NON-NEGOTIABLE) — `/speckit-tasks` MUST sequence test-writing tasks ahead of their
implementation counterparts, not alongside or after them.

## Docker, CI/CD & Kubernetes-Readiness

- **Docker** (Research #16): `backend.Dockerfile` builds one image used for both `api` and
  `worker` (different `CMD`/entrypoint arg selects the role); `frontend.Dockerfile` is a
  standard multi-stage Next.js production build. `infra/docker/docker-compose.yml` runs the full
  stack locally (postgres, redis, minio, api, worker, frontend) for development and for CI
  integration-test service containers.
- **CI/CD** (Research #15): GitHub Actions, staged — (1) lint + type-check + unit tests on every
  push; (2) integration/contract tests against ephemeral Postgres+Redis on every push; (3) build
  and push versioned images for api/worker/frontend on merge to `main`. Deployment/promotion to
  staging or production is intentionally left as a documented follow-on (not part of this
  planning phase's output), consistent with "do not implement yet."
- **Kubernetes-readiness** (Research #16): the plan's shape is one Deployment per image
  (api/worker/frontend) with independent replica counts, a Service+Ingress in front of
  api/frontend, ConfigMap for non-secret config and Secret for credentials, liveness/readiness
  probes wired to `/healthz`/`/readyz`, and a documented future HPA hook on worker queue depth
  (e.g., via KEDA scaling on Redis queue length) once real production load data exists to tune
  it. Manifests themselves are Future implementation artifacts, not produced by this plan.
- **Environment configuration**: one `Settings` class per deployable (`api`, `worker`, shared
  `core` settings) via `pydantic-settings`, validated at process startup (fail fast on missing/
  malformed config) rather than failing later on first use.

## Scalability & Performance

- **Horizontal scaling**: API replicas are stateless (session state lives in Postgres/JWT, not
  in-process), so scaling is a replica-count change; worker replicas scale independently per
  queue (NFR-005).
- **Parallelism path** (Future, FR-076): the `execution` orchestrator's per-test-case loop is
  already structured so cases are independent units of work; enabling parallel execution within
  a run is a Future change to how the orchestrator enqueues per-case sub-jobs, not a redesign of
  `TestCase`/`TestResult`.
- **Caching** (NFR-008): Redis caches rarely-changing, frequently-read data (Organization plan/
  limits, project metadata) with short TTLs and explicit invalidation on write — introduced only
  where a specific read path is demonstrably hot, not blanket-applied.
- **Performance budgets**: NFR-001–NFR-003/SC-003/SC-004/SC-006 are the concrete targets this
  architecture is designed against; denormalized counters (Database Design) and background-only
  execution (NFR-004) are the two biggest structural contributors to meeting them.

## Accessibility & Responsive UI Strategy

Covered in full under Frontend Architecture above (Component inventory's states, Responsive
layout strategy, Dark/light theme architecture, Accessibility strategy subsections) — not
repeated here to avoid duplication between the two sections of this document.

## Development Workflow & Local Development Setup

Full runnable steps are in `quickstart.md` (Phase 1). Summary:

- `docker-compose up` in `infra/docker/` brings up Postgres, Redis, MinIO, the API, one worker,
  and the frontend dev server together, so a new contributor reaches a working full stack with
  one command.
- Backend: `uv`-managed virtual environment, Alembic migrations run automatically on container
  start in dev (explicitly manual/gated in CI and production).
- Frontend: standard `npm install && npm run dev` against the local API.
- The Spec Kit lifecycle (`/speckit-specify` → `/speckit-plan` → `/speckit-tasks` →
  `/speckit-implement`) remains the required workflow per the constitution's Development
  Workflow & Review Process section — this plan is the direct input to the next `/speckit-tasks`
  invocation.

---

## Complexity Tracking

*No entries.* The Constitution Check above found no principle violations requiring
justification. Every non-trivial infrastructure choice (RLS as a second isolation layer, a
three-queue worker split, Postgres RLS's `current_setting` pattern) is tied in `research.md` to
a specific, current spec requirement rather than speculative future-proofing, which is the bar
the constitution's Simplicity principle sets for justified complexity.
