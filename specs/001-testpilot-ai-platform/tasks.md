# Tasks: TestPilot AI — AI-Powered Web Application Testing Platform

**Input**: Design documents from `specs/001-testpilot-ai-platform/` (plan.md, spec.md,
research.md, data-model.md, contracts/, quickstart.md)

**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅,
quickstart.md ✅

**Tests**: INCLUDED. The project constitution (Principle III, NON-NEGOTIABLE) mandates
Test-First development — a failing test MUST exist, be reviewed, and be confirmed failing
before its implementation task begins. Every phase below therefore includes test tasks ahead of
their corresponding implementation tasks, not as an optional add-on.

**Organization**: Primary organization is by user story (spec.md US1–US12), exactly as the
Task Generation Rules require. The phase list and numbering below follow the 26 named phases
requested for this feature, which happen to align closely with spec.md's user stories — the
mapping is made explicit in the table below so traceability is never ambiguous.

## Format: `[ID] [P?] [Story?] [Type] Description — file path`

- **[P]**: Can run in parallel (different files, no unmet dependency)
- **[Story]**: Maps to a spec.md user story (US1–US12); omitted for Setup/Foundational/
  cross-cutting phases per the format rules
- **[Type]**: One of `Backend`, `Frontend`, `AI`, `DB`, `Testing`, `DevOps`, `Docs` — satisfies
  the requirement that every task states its category
- Every task description ends with `(Req: ...)` citing the spec.md requirement/success-criterion
  ID(s) it implements, and a `file path` for where the work lands

## Phase ↔ User Story Mapping

| Phase | Title | Story | MVP? |
|---|---|---|---|
| 1 | Project foundation & dev environment | — (Setup) | Yes |
| 2 | Design system & UI/UX foundation | — (Foundational) | Yes |
| 3 | Landing page | — (unlabeled; supports go-to-market, not a numbered spec story) | Yes |
| 4 | Authentication & user management | **US1** | Yes |
| 5 | SaaS dashboard shell | — (Foundational; every story's UI depends on it) | Yes |
| 6 | Organizations/workspaces & permissions | **US11** (Future) + org-scoping infra | Partial |
| 7 | Project management | **US2** | Yes |
| 8 | Test case management (library) | **US6** | Yes |
| 9 | AI test-case generation | **US3** | Yes |
| 10 | Playwright browser automation | — (Foundational engine used by US3 + US4) | Yes |
| 11 | Test execution engine | **US4** | Yes |
| 12 | Test results & screenshots | — (part of US4, split out per request) | Yes |
| 13 | AI failure analysis | **US5** | Yes |
| 14 | Bug/issue management | **US7** | Yes |
| 15 | AI QA Assistant | **US10** (Future) | No |
| 16 | Reports & analytics | **US8** | Yes (basic); trend/rollup Future |
| 17 | Notifications | **US9** | Yes |
| 18 | API layer hardening | — (cross-cutting) | Yes |
| 19 | Database & migrations hardening | — (cross-cutting) | Yes |
| 20 | Security & validation hardening | — (cross-cutting) | Yes |
| 21 | Automated testing infrastructure | — (cross-cutting) | Yes |
| 22 | Performance & observability | — (cross-cutting) | Yes |
| 23 | Docker & local deployment | — (cross-cutting) | Yes |
| 24 | CI/CD | — (cross-cutting) | Yes |
| 25 | Kubernetes readiness | — (cross-cutting) | Yes |
| 26 | Final integration, QA & release prep | — (cross-cutting) | Yes |

**Important build-order note (read before executing sequentially)**: Phases are numbered by
*feature area*, per the request, not strictly by build dependency. Two adjustments matter:
1. **Phase 9 (AI generation) depends on Phase 10 (Playwright engine)**: the AI generation
   library's site-analysis step reuses the `BrowserAutomationEngine` core page-load capability
   (plan.md, AI Test-Case Generation Architecture). Build Phase 10's engine-core tasks
   (T0xx, flagged below) before Phase 9's crawl task, even though Phase 9 is numbered first.
2. **Phases 1, 2, and the data/API "spine"**: Phase 1 includes the minimum backend/DB/API
   scaffolding every later phase needs (DB engine/session, base models for identity+tenancy,
   error handling, health checks, app factory). Phases 18 ("API layer") and 19 ("Database and
   migrations") are a **hardening/consolidation pass** over what every feature phase already
   built incrementally — not the first time the database or API are touched. This keeps every
   feature phase (4, 7–9, 11–17) genuinely independently buildable and testable as it's
   completed, per the Task Generation Rules, while still giving the requested phases their own
   dedicated hardening work near the end.

**CLI Interface placement (constitution Principle II)**: per a post-generation `/speckit-analyze`
finding, CLI commands are **not** consolidated into one end-of-project task. Each domain's CLI
command is built as its own small, tested task immediately after that domain's service layer
lands in its own feature phase: T243 (billing) in Phase 6, T245 (projects) in Phase 7, T247
(test cases) in Phase 8, T249 (AI generation) in Phase 9, T251 (test runs) in Phase 11, T253
(AI analysis) in Phase 13, T255 (reports) in Phase 16. T238 in Phase 26 only assembles these
already-built, already-tested commands into one distributable `testpilot-cli` entrypoint — it is
final packaging, not first implementation. No CLI commands were added for domains the
specification and quickstart.md do not require one for (auth, issues, notifications,
organizations beyond billing) — see the per-task rationale where each CLI task appears. Per the
constitution's exact wording ("CLIs MUST support both a human-readable output format and a JSON
output format"), every one of T243, T245, T247, T249, T251, T253, and T255 implements both
output modes for every subcommand it adds — this applies uniformly and is stated once here
rather than repeated in each task line.

## Path Conventions

Per plan.md's Project Structure: `backend/src/testpilot/<library>/`, `backend/tests/`,
`frontend/src/`, `frontend/tests/`, `infra/`. All paths below are repo-relative.

---

## Phase 1: Project Foundation & Development Environment (Setup)

**Purpose**: Monorepo scaffolding and the minimum backend/DB/API spine every later phase needs.

- [X] T001 Create monorepo directory structure per plan.md Project Structure (`backend/`, `frontend/`, `infra/`) (Req: plan.md Project Structure)
- [X] T002 [P] Initialize backend Python project with `uv`: `pyproject.toml` with FastAPI, SQLModel, Alembic, asyncpg, RQ, Playwright, passlib+argon2-cffi, pydantic-settings, slowapi — backend/pyproject.toml (Req: research.md #1–#2)
- [X] T003 [P] Initialize frontend Next.js (App Router) + TypeScript + Tailwind project — frontend/package.json, frontend/next.config.ts, frontend/tailwind.config.ts (Req: research.md #9)
- [X] T004 [P] Configure backend lint/format/type-check (ruff, mypy) — backend/pyproject.toml (Req: constitution Technology & Quality Constraints)
- [X] T005 [P] Configure frontend lint/format (ESLint incl. eslint-plugin-jsx-a11y, Prettier) — frontend/.eslintrc.json (Req: NFR-013/NFR-014)
- [X] T006 [Backend] Create core settings module via pydantic-settings with fail-fast env validation — backend/src/testpilot/core/config.py (Req: research.md #16, SEC-004, FR-131)
- [X] T007 [Backend] Create core async DB engine/session module (SQLModel + asyncpg) — backend/src/testpilot/core/db.py (Req: research.md #2)
- [X] T008 [Backend] Create core base SQLModel mixins (UUID PK, `organization_id`, `created_at`/`updated_at`) — backend/src/testpilot/core/models.py (Req: data-model.md shared-column convention)
- [X] T009 [DB] Initialize Alembic migrations framework against the core engine — backend/alembic/env.py, backend/alembic.ini (Req: research.md #2)
- [X] T010 [Backend] Create shared domain exception types + FastAPI exception-handler wiring producing the `{"error": {...}}` envelope — backend/src/testpilot/core/exceptions.py (Req: plan.md Error Handling & Validation, NFR-017)
- [X] T011 [Backend] Create FastAPI app factory with correlation-ID middleware and CORS — backend/src/testpilot/api/main.py (Req: NFR-009)
- [X] T012 [Backend] Implement `GET /healthz` and `GET /readyz` (DB+Redis reachability) — backend/src/testpilot/api/v1/health.py (Req: FR-137, NFR-010)
- [X] T013 [P] [DevOps] Create `.env.example` documenting every required environment variable — infra/docker/.env.example (Req: SEC-004)
- [X] T014 [P] [Docs] Write root README describing repo layout and the Spec Kit workflow — README.md (Req: constitution Development Workflow)

**Checkpoint**: `uvicorn testpilot.api.main:app` boots and `/healthz`/`/readyz` respond; frontend dev server boots to a blank Next.js shell.

---

## Phase 2: Design System & UI/UX Foundation (Foundational — Frontend)

**Purpose**: The shared component/token layer every page in every later phase is built from.
**⚠️ CRITICAL**: No page-building task in Phases 3–17 should start before this phase completes.

- [X] T015 [P] [Frontend] Define design tokens (color, spacing, radius, typography scale, status/severity/priority color tokens) as CSS custom properties — frontend/src/styles/tokens.css (Req: UX-001, UX-003)
- [X] T016 [Frontend] Wire Tailwind `theme.extend` to consume the token file — frontend/tailwind.config.ts (Req: UX-001) — depends on T015
- [X] T017 [P] [Frontend] Implement `ThemeProvider` (light/dark via `data-theme`, `prefers-color-scheme` default, persisted override) — frontend/src/lib/theme-provider.tsx (Req: UX-007)
- [X] T018 [P] [Frontend] Implement typed API client (fetch wrapper, `{"error":...}` envelope parsing, Bearer header attach, 401→refresh retry) — frontend/src/lib/api-client.ts (Req: plan.md API Design, SEC-008)
- [X] T019 [P] [Frontend] Configure TanStack Query provider with org/entity-namespaced query-key conventions — frontend/src/lib/query-client.tsx (Req: research.md #10)
- [X] T020 [P] [Frontend] Build `Button` primitive (variants, sizes, loading state) — frontend/src/components/Button.tsx (Req: UX-001)
- [X] T021 [P] [Frontend] Build form primitives `TextField`, `Select`, `TagInput`, `URLField` (client-side well-formedness check) — frontend/src/components/form/ (Req: UX-001, FR-026)
- [X] T022 [P] [Frontend] Build `Dialog` primitive on Radix Dialog (focus trap, ARIA) — frontend/src/components/Dialog.tsx (Req: NFR-013/014)
- [X] T023 [P] [Frontend] Build `DropdownMenu` primitive on Radix DropdownMenu — frontend/src/components/DropdownMenu.tsx (Req: NFR-013/014)
- [X] T024 [P] [Frontend] Build `Tabs` primitive on Radix Tabs — frontend/src/components/Tabs.tsx (Req: NFR-013/014)
- [X] T025 [P] [Frontend] Build `Tooltip` primitive on Radix Tooltip — frontend/src/components/Tooltip.tsx (Req: NFR-013/014)
- [X] T026 [P] [Frontend] Build `Toast` system on Radix Toast for transient success/error messages — frontend/src/components/Toast.tsx (Req: UX-006)
- [X] T027 [P] [Frontend] Build `StatusBadge`, `SeverityBadge`, `PriorityBadge` (color+icon+text, never color alone) — frontend/src/components/badges/ (Req: UX-003, NFR-014)
- [X] T028 [P] [Frontend] Build `Card` and `StatCard` components — frontend/src/components/Card.tsx, StatCard.tsx (Req: UX-001)
- [X] T029 [Frontend] Build `DataTable` with built-in search/filter/sort, mobile card-layout fallback — frontend/src/components/DataTable.tsx (Req: UX-008, NFR-015) — depends on T020–T027
- [X] T030 [P] [Frontend] Build `EmptyState`, `LoadingState` (content-shaped skeletons), `ErrorState` components — frontend/src/components/states/ (Req: UX-005, NFR-016)
- [X] T031 [P] [Frontend] Build `ConfirmDialog` for destructive actions — frontend/src/components/ConfirmDialog.tsx (Req: FR-029)
- [X] T032 [P] [Frontend] Build `ProgressBar` / `RunProgressRing` live-progress components — frontend/src/components/Progress.tsx (Req: UX-004)
- [X] T033 [Frontend] Build `SidebarNav` and `Topbar` layout components with responsive collapse-to-drawer behavior — frontend/src/components/layout/SidebarNav.tsx, Topbar.tsx (Req: FR-020, NFR-015, UX-002) — depends on T020–T027
- [X] T034 [P] [DevOps] Configure Vitest + React Testing Library — frontend/vitest.config.ts (Req: research.md #14)
- [X] T035 [P] [Testing] Unit tests for design-system primitives covering state variants and ARIA roles — frontend/tests/unit/components/ (Req: NFR-013/014) — depends on T034

**Checkpoint**: A fully working component set exists; any later page task can compose from `frontend/src/components/` without inventing new primitives.

---

## Phase 3: Landing Page (Public, Unauthenticated)

**Goal**: A real marketing entry point exists so the product isn't login-wall-only, per the "real
SaaS product" mandate.

- [X] T036 [P] [Frontend] Build marketing route-group layout (public nav + footer, no sidebar) — frontend/src/app/(marketing)/layout.tsx (Req: plan.md Route Map) — depends on T033
- [X] T037 [Frontend] Build landing page (hero, feature highlights, CTA into `/signup`) — frontend/src/app/(marketing)/page.tsx (Req: Product Overview) — depends on T036
- [X] T038 [P] [Frontend] Build pricing page rendering `GET /billing/plans` — frontend/src/app/(marketing)/pricing/page.tsx (Req: contracts/billing-api.md) — depends on T036, and the billing-plans-list endpoint built in Phase 6
- [X] T039 [P] [Frontend] Add SEO metadata (title/description/OG tags) to the marketing layout — frontend/src/app/(marketing)/layout.tsx (Req: UX-001)
- [X] T040 [Testing] E2E test: landing page loads and its primary CTA navigates to `/signup` — frontend/tests/e2e/landing.spec.ts (Req: research.md #14) — depends on T037

**Checkpoint**: `/` and `/pricing` render without authentication.

---

## Phase 4: Authentication and User Management, User Story 1, Priority P1, MVP

**Goal**: A visitor can sign up (auto-creating their personal Organization), log in/out, and
recover a forgotten password; every later phase depends on this working.

**Independent Test**: Sign up, then logout, then login, then forgot-password, then
reset-password, then login-with-new-password, entirely via the API/UI, with no other feature
built yet.

### Tests for User Story 1 (write first, confirm failing)

- [X] T046 [P] [US1] [Testing] Contract test: POST /auth/signup, including duplicate-email 409 and weak-password 422, backend/tests/contract/test_auth_signup.py (Req: contracts/auth-api.md)
- [X] T047 [P] [US1] [Testing] Contract test: POST /auth/login, POST /auth/logout, POST /auth/refresh, backend/tests/contract/test_auth_login.py (Req: contracts/auth-api.md)
- [X] T051 [P] [US1] [Testing] Contract test: POST /auth/forgot-password, POST /auth/reset-password, including expired/reused token 400, backend/tests/contract/test_auth_password_reset.py (Req: contracts/auth-api.md, spec Edge Cases)
- [X] T058 [US1] [Testing] Integration test: full signup-login-logout-forgot-password-reset flow against real Postgres, backend/tests/integration/test_auth_flow.py (Req: quickstart.md Section 3) - depends on T046, T047, T051

### Implementation for User Story 1

- [X] T041 [US1] [DB] Create organizations, memberships, subscription_plans models plus Alembic migration plus seed Free/Starter/Professional/Enterprise rows, backend/src/testpilot/orgs/models.py (Req: FR-012, FR-120, FR-121, data-model.md) - depends on T008, T009
- [X] T042 [P] [US1] [DB] Create users, refresh_tokens, password_reset_tokens models plus Alembic migration, backend/src/testpilot/auth/models.py (Req: FR-001, data-model.md) - depends on T008, T009
- [X] T043 [US1] [DB] Write the reusable Postgres RLS policy template migration and apply it to memberships, backend/alembic/versions/xxxx_rls_template.py (Req: DATA-001, SEC-011, research.md #4) - depends on T041
- [X] T044 [P] [US1] [Backend] Implement Argon2id password hashing utilities, backend/src/testpilot/auth/security.py (Req: SEC-001)
- [X] T045 [P] [US1] [Backend] Implement JWT access-token sign/verify utilities, backend/src/testpilot/auth/tokens.py (Req: SEC-002)
- [X] T048 [US1] [Backend] Implement signup logic: create user plus personal Organization plus owner Membership, assign Free plan, backend/src/testpilot/auth/service.py (Req: FR-001, FR-012, FR-119) - depends on T041, T042, T044, T046
- [X] T049 [US1] [Backend] Implement login/logout/refresh logic, session issuance and revocation, backend/src/testpilot/auth/service.py (Req: FR-002, FR-003, FR-008) - depends on T045, T047
- [X] T050 [US1] [Backend] Implement forgot/reset-password logic including transactional email send, backend/src/testpilot/auth/service.py, backend/src/testpilot/core/email.py (Req: FR-004, FR-005, INT-003) - depends on T042
- [X] T052 [US1] [Backend] Implement anti-enumeration behavior, identical response and timing, for login and forgot-password, backend/src/testpilot/auth/service.py (Req: FR-010) - depends on T049, T050
- [X] T053 [US1] [Backend] Wire slowapi rate limiting on signup/login/forgot-password endpoints, backend/src/testpilot/api/deps.py (Req: SEC-009, FR-009) - depends on T011
- [X] T054 [US1] [Backend] Implement current_user and current_organization dependencies plus per-request RLS session-context setter, backend/src/testpilot/api/deps.py (Req: research.md #4, FR-133, SEC-003) - depends on T043, T045
- [X] T055 [US1] [Backend] Implement routes for signup/login/logout/refresh/forgot-password/reset-password, backend/src/testpilot/api/v1/auth.py (Req: contracts/auth-api.md) - depends on T048, T049, T050, T052, T053, T054
- [X] T056 [US1] [Backend] Implement GET/PATCH /auth/me, change-password, sessions list/revoke endpoints, backend/src/testpilot/api/v1/auth.py (Req: FR-006, FR-008) - depends on T055
- [X] T241 [US1] [Backend] Add DELETE /auth/me to contracts/auth-api.md and implement it: anonymize the user row (tombstone email, is_active=false) while preserving referential integrity of Organization-owned records they created, backend/src/testpilot/auth/service.py, backend/src/testpilot/api/v1/auth.py, specs/001-testpilot-ai-platform/contracts/auth-api.md (Req: DATA-004) - depends on T056, added during the post-generation requirement-coverage audit
- [X] T057 [US1] [Backend] Wire audit_log_entries writes for login/logout/failed-login/password-reset events, backend/src/testpilot/audit/service.py (Req: SEC-010, FR-128) - depends on T055
- [X] T059 [P] [US1] [Frontend] Build the (auth) route-group layout, centered card, no sidebar, frontend/src/app/(auth)/layout.tsx (Req: plan.md Route Map) - depends on T033
- [X] T060 [US1] [Frontend] Build signup page, frontend/src/app/(auth)/signup/page.tsx (Req: FR-001) - depends on T059, T018, T055
- [X] T061 [US1] [Frontend] Build login page, frontend/src/app/(auth)/login/page.tsx (Req: FR-002) - depends on T059, T018, T055
- [X] T062 [US1] [Frontend] Build forgot-password page, frontend/src/app/(auth)/forgot-password/page.tsx (Req: FR-004) - depends on T059, T018, T055
- [X] T063 [US1] [Frontend] Build reset-password page, token read from query param, frontend/src/app/(auth)/reset-password/page.tsx (Req: FR-005) - depends on T059, T018, T055
- [X] T064 [US1] [Frontend] Implement auth session hook/guard, redirects unauthenticated users, for reuse by the dashboard layout, frontend/src/lib/auth.ts (Req: FR-007) - depends on T018, T056
- [X] T065 [US1] [Frontend] Build Settings, Profile page, name/email/password, frontend/src/app/(dashboard)/settings/profile/page.tsx (Req: FR-006) - depends on T056, T064
- [X] T066 [US1] [Frontend] Build Settings, Security page, active sessions, logout-everywhere, frontend/src/app/(dashboard)/settings/security/page.tsx (Req: FR-008) - depends on T056, T064
- [X] T067 [US1] [Testing] E2E test: signup-logout-login-forgot-password-reset flow, frontend/tests/e2e/auth.spec.ts (Req: quickstart.md Section 3) - depends on T060, T061, T062, T063

**Checkpoint**: User Story 1 fully functional and independently testable. A user can sign up, use the product's auth surface end-to-end, and reach a still-empty dashboard.

---

## Phase 5: SaaS Dashboard Shell, Foundational, every authenticated page depends on it

**Goal**: The authenticated app shell (sidebar, topbar, org context, Overview) that every
subsequent feature's pages mount into.

- [X] T068 [Frontend] Build the (dashboard) route-group layout: auth guard, org context, SidebarNav plus Topbar wiring, frontend/src/app/(dashboard)/layout.tsx (Req: FR-007, FR-020, FR-024) - depends on T033, T064
- [X] T069 [Backend] Implement GET /organizations/current, backend/src/testpilot/api/v1/organizations.py (Req: contracts/organizations-api.md) - depends on T054
- [X] T070 [Frontend] Build Overview page with stat cards, recent activity, and a first-run empty state, frontend/src/app/(dashboard)/overview/page.tsx (Req: FR-021, FR-022) - depends on T068, T028, T030, T069
- [X] T071 [Frontend] Implement notification bell plus slide-over shell in Topbar, data wiring lands in Phase 17, frontend/src/components/layout/NotificationBell.tsx (Req: FR-115) - depends on T068
- [X] T072 [Testing] E2E test: authenticated user lands on Overview after login and sees sidebar nav for every MVP section, frontend/tests/e2e/dashboard-shell.spec.ts (Req: FR-020, FR-021) - depends on T070

**Checkpoint**: A logged-in user reaches a real, if mostly empty, dashboard shell with working navigation.

---

## Phase 6: Organizations/Workspaces and Permissions, User Story 11, Priority P3 Future, plus Tenancy Hardening

**Goal**: Org-level settings and billing/usage visibility for the MVP's single-member
Organizations, plus the reusable RLS pattern extended to every tenant table, with the
multi-member/invite surface scaffolded, not functional, for Future Scope.

**Independent Test**: Org owner edits workspace name and views plan/usage on the Billing
settings page; a second Organization's data is provably invisible to the first, via an RLS test.

### Tests for this phase

- [X] T079 [P] [Testing] Contract test: GET/PATCH /organizations/current, GET .../members, GET .../billing, GET /billing/plans, including 402 plan_limit_exceeded shape, backend/tests/contract/test_organizations_billing.py (Req: contracts/organizations-api.md, contracts/billing-api.md)
- [ ] T080 [Testing] Integration test: RLS denies cross-Organization reads on projects and test_cases using two seeded Organizations, backend/tests/integration/test_rls_isolation.py (Req: SEC-011, FR-014, quickstart.md Section 12) - depends on T073
- [X] T242 [P] [Testing] CLI test: testpilot-cli billing show and set-plan commands, using Typer's CliRunner, backend/tests/unit/cli/test_billing_cli.py (Req: constitution Principle II, quickstart.md Section 13) - depends on T077

### Implementation for this phase

- [X] T073 [DB] Extend the Phase 4 RLS policy template to every tenant table that exists so far and document the pattern new tables must follow, backend/alembic/versions/xxxx_rls_pattern.py (Req: DATA-001, SEC-011, FR-014) - depends on T043
- [X] T074 [Backend] Implement PATCH /organizations/current, owner/admin only, backend/src/testpilot/api/v1/organizations.py (Req: FR-013) - depends on T069
- [X] T075 [Backend] Implement GET /organizations/current/members, MVP always one row, backend/src/testpilot/api/v1/organizations.py (Req: FR-015) - depends on T069
- [X] T076 [P] [DB] Create usage_records model plus migration, granular enough per Organization/period/metric to reconstruct what consumed the usage, backend/src/testpilot/billing/models.py (Req: data-model.md usage_records, DATA-007) - depends on T041
- [X] T077 [Backend] Implement billing library: check_and_reserve_usage, plan-limit lookup, backend/src/testpilot/billing/service.py (Req: FR-121 to FR-127) - depends on T076
- [X] T078 [Backend] Implement GET /organizations/current/billing, GET /billing/plans, backend/src/testpilot/api/v1/billing.py (Req: contracts/billing-api.md) - depends on T077
- [X] T243 [Backend] CLI: testpilot-cli billing show (plan/usage) and set-plan (admin override, used by quickstart.md Section 13 for plan-limit testing), backend/src/testpilot/cli/billing.py (Req: constitution Principle II, FR-125, quickstart.md Section 13) - depends on T077, T242
- [X] T081 [P] [Frontend] Build Settings, Organization page, workspace name, frontend/src/app/(dashboard)/settings/organization/page.tsx (Req: FR-013) - depends on T074, T064
- [X] T082 [P] [Frontend] Build Settings, Billing page, plan plus usage vs limits, frontend/src/app/(dashboard)/settings/billing/page.tsx (Req: FR-127) - depends on T078, T064
- [X] T083 [P] [US11] [Frontend] Build Settings, Members page scaffold, Future invite/role UI shown as a clearly-labeled coming-soon state at MVP, frontend/src/app/(dashboard)/settings/members/page.tsx (Req: FR-016 to FR-019, Future Scope) - depends on T075, T064
- [X] T084 [US11] [DB] Add the invitations table, Future schema per data-model.md, and stubs for POST /organizations/current/invitations and DELETE /organizations/current/members/{user_id}, both returning 501 not_implemented at MVP, backend/src/testpilot/orgs/models.py, backend/src/testpilot/api/v1/organizations.py (Req: FR-016, FR-018, Future Scope) - depends on T075

**Checkpoint**: Org settings/billing are real and RLS is proven to isolate tenants; multi-member collaboration is visibly scaffolded but explicitly inert, matching the MVP/Future split.

---

## Phase 7: Project Management, User Story 2, Priority P1, MVP

**Goal**: A user can create, edit, archive, and delete projects with a validated, SSRF-safe URL.

**Independent Test**: Create a project with a real URL (succeeds, appears in list); attempt one
with a private-IP URL (rejected); edit, archive, and delete it, independent of any test-case or
test-run feature existing yet.

### Tests for User Story 2

- [X] T085 [P] [US2] [Testing] Contract test: GET/POST /projects, PATCH, archive/unarchive, DELETE, backend/tests/contract/test_projects.py (Req: contracts/projects-api.md)
- [X] T086 [P] [US2] [Testing] Unit tests for validate_public_url, including private/loopback/reserved-range rejection and malformed URL, backend/tests/unit/test_url_validation.py (Req: FR-035, SEC-006)
- [X] T087 [US2] [Testing] Integration test: create project with plan limit of 1, second creation blocked with 402, backend/tests/integration/test_project_plan_limits.py (Req: FR-123) - depends on T077
- [X] T244 [P] [US2] [Testing] CLI test: testpilot-cli projects list/create/archive commands, using Typer's CliRunner, backend/tests/unit/cli/test_projects_cli.py (Req: constitution Principle II) - depends on T090

### Implementation for User Story 2

- [X] T088 [US2] [DB] Create projects model plus migration plus RLS policy, backend/src/testpilot/projects/models.py (Req: data-model.md projects, DATA-001) - depends on T073
- [X] T089 [US2] [Backend] Implement validate_public_url SSRF guard, DNS resolution plus private/loopback/link-local/reserved range rejection, backend/src/testpilot/projects/url_validation.py (Req: FR-035, SEC-006) - depends on T086
- [X] T090 [US2] [Backend] Implement projects library: create/edit/archive/unarchive/delete with plan-limit check and cascading delete of test cases/runs/results/artifacts on hard delete, backend/src/testpilot/projects/service.py (Req: FR-025 to FR-032, FR-123, DATA-005) - depends on T088, T089, T077
- [X] T091 [US2] [Backend] Implement project routes, backend/src/testpilot/api/v1/projects.py (Req: contracts/projects-api.md) - depends on T090, T085
- [X] T245 [US2] [Backend] CLI: testpilot-cli projects list/create/archive, wrapping the projects library directly (not the HTTP API), backend/src/testpilot/cli/projects.py (Req: constitution Principle II) - depends on T090, T244
- [X] T092 [P] [US2] [Frontend] Build projects list page, frontend/src/app/(dashboard)/projects/page.tsx (Req: FR-033) - depends on T068, T029, T091
- [X] T093 [US2] [Frontend] Build new-project page, frontend/src/app/(dashboard)/projects/new/page.tsx (Req: FR-025) - depends on T068, T021, T091
- [X] T094 [US2] [Frontend] Build project detail page, info plus testing history, frontend/src/app/(dashboard)/projects/[projectId]/page.tsx (Req: FR-030) - depends on T091
- [X] T095 [US2] [Frontend] Build project settings page, edit/archive/delete with ConfirmDialog, frontend/src/app/(dashboard)/projects/[projectId]/settings/page.tsx (Req: FR-027 to FR-029, FR-031) - depends on T031, T091
- [X] T096 [US2] [Frontend] Build project-context layout providing name/URL/status to nested routes, frontend/src/app/(dashboard)/projects/[projectId]/layout.tsx (Req: FR-024) - depends on T094
- [X] T097 [US2] [Testing] E2E test: create project with a private-IP URL, rejected, then a valid URL, accepted and appears in list, frontend/tests/e2e/projects.spec.ts (Req: quickstart.md Section 4) - depends on T092, T093

**Checkpoint**: User Story 2 fully functional and independently testable, layered on top of Story 1's auth/org foundation.

---

## Phase 8: Test Case Management, User Story 6, Priority P2, MVP

**Goal**: A searchable, filterable, taggable library of test cases per project, supporting both
manual and (later, Phase 9) AI-generated cases on the same data model.

**Independent Test**: Manually create several test cases with varying priority/severity/status/
tags, then verify search, each filter, and sort each return correct results.

### Tests for User Story 6

- [X] T098 [P] [US6] [Testing] Contract test: test-cases CRUD, approve/reject, list/filter/search, backend/tests/contract/test_testcases.py (Req: contracts/test-cases-api.md)
- [X] T099 [US6] [Testing] Integration test: full-text search plus tag/priority/severity/status filters against seeded cases, backend/tests/integration/test_testcase_search.py (Req: FR-050, FR-051)
- [X] T246 [P] [US6] [Testing] CLI test: testpilot-cli testcases list/create/approve/reject commands, using Typer's CliRunner, backend/tests/unit/cli/test_testcases_cli.py (Req: constitution Principle II) - depends on T101

### Implementation for User Story 6

- [X] T100 [US6] [DB] Create test_cases and test_steps models plus migration, generated search_vector column with GIN index, tags GIN index, plus RLS, backend/src/testpilot/testcases/models.py (Req: data-model.md test_cases/test_steps) - depends on T073, T088
- [X] T101 [US6] [Backend] Implement testcases library: CRUD, approve/reject, tag management, search/filter/sort query builder, backend/src/testpilot/testcases/service.py (Req: FR-041 to FR-044, FR-049 to FR-057) - depends on T100
- [X] T102 [US6] [Backend] Implement test-case routes, backend/src/testpilot/api/v1/testcases.py (Req: contracts/test-cases-api.md) - depends on T101, T098
- [X] T247 [US6] [Backend] CLI: testpilot-cli testcases list/create/approve/reject, wrapping the testcases library directly, backend/src/testpilot/cli/testcases.py (Req: constitution Principle II) - depends on T101, T246
- [X] T103 [P] [US6] [Frontend] Build TestStepEditor component, structured step builder, frontend/src/components/TestStepEditor.tsx (Req: FR-053) - depends on T021
- [X] T104 [US6] [Frontend] Build test case library list page, DataTable with search/filter/sort/tags, frontend/src/app/(dashboard)/projects/[projectId]/test-cases/page.tsx (Req: FR-049 to FR-052) - depends on T029, T096, T102
- [X] T105 [US6] [Frontend] Build manual test case creation page, frontend/src/app/(dashboard)/projects/[projectId]/test-cases/new/page.tsx (Req: FR-053) - depends on T103, T102
- [X] T106 [US6] [Frontend] Build test case detail/edit page, edit/approve/reject actions, frontend/src/app/(dashboard)/projects/[projectId]/test-cases/[testCaseId]/page.tsx (Req: FR-041, FR-042) - depends on T103, T102
- [X] T107 [US6] [Testing] E2E test: create a manual test case, filter the library by tag and priority, approve then reject a case, frontend/tests/e2e/test-cases-library.spec.ts (Req: quickstart.md Section 8) - depends on T104, T105, T106

**Checkpoint**: A project's test case library is fully manageable even before AI generation exists, satisfying independent testability.

---

## Phase 9: AI Test-Case Generation, User Story 3, Priority P1, MVP

**Goal**: Given a project URL, AI analyzes public pages and generates reviewable test cases
covering positive, negative, and edge-case flows.

**Independent Test**: Trigger generation on a project with a real URL; poll to completion;
verify the resulting cases include a mix of flow types with non-empty purpose explanations; edit,
approve, reject, and regenerate.

**Dependency note**: The site-analysis step below (T115) needs the `BrowserAutomationEngine`
core interface and its page-load capability, which are built in **Phase 10** (T125 interface,
T126 Playwright adapter). Build those two Phase 10 tasks before T115, even though Phase 10 is
numbered after this phase in the document (see the build-order note at the top of this file).

### Tests for User Story 3

- [X] T108 [P] [US3] [Testing] Contract test: POST .../test-cases/generate, GET generation status, POST regenerate, including 409 concurrent-generation, backend/tests/contract/test_ai_generation.py (Req: contracts/test-cases-api.md)
- [X] T109 [US3] [Testing] Unit tests for the fake LLMProvider adapter's structured-output contract, backend/tests/unit/test_ai_provider_contract.py (Req: contracts/ai-provider-adapter.md)
- [X] T110 [US3] [Testing] Integration test: generation produces a positive/negative/edge-case mix with non-empty purpose text per case, backend/tests/integration/test_ai_generation_flow.py (Req: FR-039, FR-040)
- [X] T248 [P] [US3] [Testing] CLI test: testpilot-cli ai generate-tests command, using Typer's CliRunner against the fake LLMProvider adapter, backend/tests/unit/cli/test_ai_generate_cli.py (Req: constitution Principle II) - depends on T112, T116

### Implementation for User Story 3

- [X] T111 [US3] [AI] Define the LLMProvider Protocol, generate_test_cases plus analyze_failure plus chat, backend/src/testpilot/ai_provider/base.py (Req: contracts/ai-provider-adapter.md, NFR-018, INT-002)
- [X] T112 [US3] [AI] Implement a fake in-memory LLMProvider adapter for tests, backend/src/testpilot/ai_provider/fake.py (Req: contracts/ai-provider-adapter.md) - depends on T111
- [X] T113 [US3] [AI] Implement the concrete cloud LLMProvider adapter with structured-output enforcement and a typed AIProviderError, backend/src/testpilot/ai_provider/cloud.py (Req: research.md #7) - depends on T111
- [X] T114 [US3] [DB] Create generation_runs model plus migration plus RLS, backend/src/testpilot/ai_generation/models.py (Req: data-model.md generation_runs, FR-047) - depends on T073, T100
- [X] T115 [US3] [AI] Implement the ai_generation site-analysis step, reusing the BrowserAutomationEngine core page-load capability, plus prompt construction, backend/src/testpilot/ai_generation/analysis.py (Req: plan.md AI Test-Case Generation Architecture) - depends on T125, T126 (Phase 10)
- [X] T116 [US3] [AI] Implement ai_generation orchestration: generate_for_project, persist draft test cases/steps exactly as the provider returned them, concurrency guard, backend/src/testpilot/ai_generation/service.py (Req: FR-036 to FR-047, DATA-006) - depends on T113, T114, T115, T101
- [X] T117 [US3] [Backend] Implement generate/regenerate endpoints plus generation-run status endpoint, backend/src/testpilot/api/v1/testcases.py (Req: contracts/test-cases-api.md) - depends on T116, T108
- [X] T118 [US3] [Backend] Implement the ai-generation worker job handler, GenerateTestCasesJob, backend/src/testpilot/worker/jobs/generate_test_cases.py (Req: contracts/worker-jobs.md) - depends on T116
- [X] T119 [US3] [Backend] Wire the ai_operations plan-limit check before enqueueing generation, backend/src/testpilot/ai_generation/service.py (Req: FR-123 to FR-125) - depends on T077, T116
- [X] T249 [US3] [AI] CLI: testpilot-cli ai generate-tests <project_id>, enqueues a generation job and prints the generation_run id/status, wrapping ai_generation directly, backend/src/testpilot/cli/ai.py (Req: constitution Principle II) - depends on T116, T119, T248
- [X] T120 [US3] [Frontend] Build the generation trigger action plus a status-polling hook, frontend/src/features/testcases/useGeneration.ts (Req: research.md #11) - depends on T019, T117
- [X] T121 [US3] [Frontend] Build the generation review queue page, approve/reject/regenerate per case, frontend/src/app/(dashboard)/projects/[projectId]/test-cases/generate/page.tsx (Req: FR-041 to FR-044) - depends on T120, T106
- [X] T122 [US3] [Testing] E2E test: trigger generation, poll to completion, review queue shows a mixed set of flow types, approve one case, frontend/tests/e2e/ai-generation.spec.ts (Req: quickstart.md Section 5) - depends on T121

**Checkpoint**: The product's core AI-generation loop works end-to-end and is independently demoable on top of Stories 1, 2, and 6.

---

## Phase 10: Playwright Browser Automation (Foundational Engine — used by Stories 3 and 4)

**Goal**: The `BrowserAutomationEngine` interface and its Playwright implementation, isolated,
timeout-bounded, and fault-tolerant, per FR-059 to FR-068.

**Note**: T125 and T126 below are the specific dependency Phase 9's T115 needs. Build this
phase's interface and adapter core before finishing Phase 9's site-analysis task if working
strictly in numeric order.

### Tests for this phase

- [X] T123 [P] [Testing] Contract/fixture test: every step-executor action_type against a local fixture page, backend/tests/contract/test_browser_engine.py (Req: contracts/browser-automation-adapter.md, FR-059 to FR-063)
- [X] T124 [Testing] Fault-injection test: context crash and missing-element cases return a structured error result rather than raising, backend/tests/contract/test_browser_engine_faults.py (Req: NFR-007, FR-075)

### Implementation for this phase

- [X] T125 [Backend] Define the BrowserAutomationEngine interface, run_test_case plus the step-executor primitives, backend/src/testpilot/execution/engine.py (Req: contracts/browser-automation-adapter.md, FR-068, NFR-019, INT-001)
- [X] T126 [Backend] Implement the Playwright adapter: pre-warmed Browser plus BrowserContext-per-test-case isolation, backend/src/testpilot/execution/playwright_engine.py (Req: research.md #6, FR-067) - depends on T125
- [X] T127 [Backend] Implement step executors: navigate, click, type, submit, backend/src/testpilot/execution/steps.py (Req: FR-059 to FR-061) - depends on T126
- [X] T128 [Backend] Implement step executors: assert_url, assert_content, assert_element, backend/src/testpilot/execution/steps.py (Req: FR-061 to FR-063) - depends on T126
- [X] T129 [Backend] Implement per-step and per-test-case timeout enforcement inside the engine, backend/src/testpilot/execution/engine.py (Req: FR-066) - depends on T127, T128
- [X] T130 [Backend] Implement the SSRF guard re-check immediately before every navigate call inside the engine boundary, backend/src/testpilot/execution/engine.py (Req: SEC-006, FR-135) - depends on T089, T126
- [X] T131 [Backend] Implement crash/fault isolation so the engine returns a structured error TestResult instead of raising, backend/src/testpilot/execution/engine.py (Req: NFR-007, FR-075) - depends on T126, T124
- [X] T132 [P] [Testing] Build a local fixture site with known, stable markup for engine tests, backend/tests/fixtures/fixture_site/ (Req: contracts/browser-automation-adapter.md Testing contract)
- [X] T133 [Testing] Stand up a local fixture-page test server for CI, backend/tests/fixtures/server.py (Req: contracts/browser-automation-adapter.md Testing contract) - depends on T132

**Checkpoint**: The engine can be driven directly in tests against the fixture site, independent of the rest of the execution orchestrator built in Phase 11.

---

## Phase 11: Test Execution Engine, User Story 4, Priority P1, MVP

**Goal**: A user selects approved test cases, starts a real browser-driven test run, and sees
live progress and pass/fail/skip results.

**Independent Test**: Select approved cases from Story 6/9, start a run, watch it reach a
terminal state with a live progress indicator, retry only the failed cases.

### Tests for User Story 4

- [X] T134 [P] [US4] [Testing] Contract test: POST/GET test-runs, retry-failed, backend/tests/contract/test_test_runs.py (Req: contracts/test-runs-api.md)
- [X] T135 [US4] [Testing] Integration test: a run of 3 test cases, 2 pass and 1 fail, produces correct summary counters, backend/tests/integration/test_execution_flow.py (Req: FR-070, FR-074)
- [X] T250 [P] [US4] [Testing] CLI test: testpilot-cli run execute/list/retry-failed commands, using Typer's CliRunner, backend/tests/unit/cli/test_run_cli.py (Req: constitution Principle II) - depends on T138, T139

### Implementation for User Story 4

- [X] T136 [US4] [DB] Create test_runs, test_run_cases, test_results models plus migration plus RLS plus denormalized summary counters, backend/src/testpilot/execution/models.py (Req: data-model.md test_runs/test_results) - depends on T073, T100
- [X] T137 [US4] [Backend] Implement the execution orchestrator: sequencing cases, updating counters, per-case fault isolation, invoked only from worker processes never inline in an API request, backend/src/testpilot/execution/runner.py (Req: FR-070, FR-075, NFR-004, NFR-006, NFR-007) - depends on T125, T136
- [X] T138 [US4] [Backend] Implement test-run creation with plan-limit check, rejecting rejected-status cases, backend/src/testpilot/execution/service.py (Req: FR-069, FR-057, FR-123) - depends on T137, T077
- [X] T139 [US4] [Backend] Implement retry-failed logic, a new run scoped to the previous run's failed case IDs, backend/src/testpilot/execution/service.py (Req: FR-073) - depends on T138
- [X] T140 [US4] [Backend] Implement test-run routes: create/list/get/retry-failed, backend/src/testpilot/api/v1/testruns.py (Req: contracts/test-runs-api.md) - depends on T138, T139, T134
- [X] T141 [US4] [Backend] Implement the test-execution worker job handler, ExecuteTestRunJob, backend/src/testpilot/worker/jobs/execute_test_run.py (Req: contracts/worker-jobs.md) - depends on T137
- [X] T251 [US4] [Backend] CLI: testpilot-cli run execute <run_id>/list/retry-failed, wrapping the execution library directly, backend/src/testpilot/cli/run.py (Req: constitution Principle II) - depends on T138, T139, T250
- [X] T142 [US4] [Frontend] Build the run-creation/select-cases page, frontend/src/app/(dashboard)/projects/[projectId]/test-runs/new/page.tsx (Req: FR-069) - depends on T104, T140
- [X] T143 [US4] [Frontend] Build the run monitor page, live polling plus RunProgressRing, frontend/src/app/(dashboard)/projects/[projectId]/test-runs/[testRunId]/page.tsx (Req: FR-071, UX-004) - depends on T032, T140
- [X] T144 [US4] [Frontend] Build the run history page, frontend/src/app/(dashboard)/projects/[projectId]/test-runs/page.tsx (Req: FR-076) - depends on T029, T140
- [X] T145 [US4] [Testing] E2E test: select cases, start a run, watch it complete, retry the failed ones, frontend/tests/e2e/test-runs.spec.ts (Req: quickstart.md Section 6) - depends on T142, T143, T144

**Checkpoint**: The full generate-then-execute loop (Stories 3 plus 4) is independently demoable end-to-end.

---

## Phase 12: Test Results and Screenshots (part of User Story 4)

**Goal**: Result detail with execution log and screenshot evidence, backed by object storage.

### Tests for this phase

- [X] T146 [P] [Testing] Contract test: result detail endpoint returns log plus artifacts with signed URLs, backend/tests/contract/test_test_results.py (Req: contracts/test-runs-api.md)
- [X] T147 [Testing] Integration test: artifact upload/retrieval round-trip via MinIO, backend/tests/integration/test_artifact_storage.py (Req: DATA-002)

### Implementation for this phase

- [X] T148 [DB] Create artifacts model plus migration plus RLS, backend/src/testpilot/execution/artifact_models.py (Req: data-model.md artifacts) - depends on T073, T136
- [X] T149 [Backend] Implement the ArtifactStorage interface, backend/src/testpilot/storage/base.py (Req: DATA-002, INT-004)
- [X] T150 [Backend] Implement the S3/MinIO adapter via boto3 plus signed URL generation, backend/src/testpilot/storage/s3.py (Req: research.md #8, SEC-013) - depends on T149
- [X] T151 [Backend] Wire engine artifact capture, screenshot-on-failure plus checkpoints, to immediate storage upload, backend/src/testpilot/execution/runner.py (Req: FR-064, spec Edge Cases) - depends on T150, T137
- [X] T152 [Backend] Implement the result detail endpoint, log plus signed artifact URLs, backend/src/testpilot/api/v1/testruns.py (Req: contracts/test-runs-api.md) - depends on T151, T146
- [X] T153 [DB] Implement the retention-purge worker job, nulls storage_key past the retention window, backend/src/testpilot/worker/jobs/purge_artifacts.py (Req: DATA-003) - depends on T148
- [X] T154 [Frontend] Build the result detail page, execution log viewer plus ScreenshotViewer lightbox, frontend/src/app/(dashboard)/projects/[projectId]/test-runs/[testRunId]/results/[testResultId]/page.tsx (Req: FR-072) - depends on T152, T143
- [X] T155 [Testing] E2E test: open a failed result and view its screenshot in the lightbox, frontend/tests/e2e/test-results.spec.ts (Req: quickstart.md Section 6) - depends on T154

**Checkpoint**: Evidence (logs, screenshots) is fully viewable per result, completing Story 4's UI surface.

---

## Phase 13: AI Failure Analysis, User Story 5, Priority P1, MVP

**Goal**: A failed test result can be explained by AI: root cause, severity, suggested fix, with
a distinct unavailable state on provider failure.

**Independent Test**: Request analysis on a failed result, see a structured explanation;
re-request, see a second versioned analysis; force the provider to fail, see a distinct
unavailable state.

### Tests for User Story 5

- [X] T156 [P] [US5] [Testing] Contract test: analyze endpoint, polling, re-request creates a new version, backend/tests/contract/test_ai_analysis.py (Req: contracts/test-runs-api.md)
- [X] T157 [US5] [Testing] Integration test: analysis-unavailable path when the provider is mocked to fail, backend/tests/integration/test_ai_analysis_failure.py (Req: FR-083)
- [X] T252 [P] [US5] [Testing] CLI test: testpilot-cli ai analyze command, using Typer's CliRunner against the fake LLMProvider adapter, backend/tests/unit/cli/test_ai_analyze_cli.py (Req: constitution Principle II) - depends on T159, T160

### Implementation for User Story 5

- [X] T158 [US5] [DB] Create ai_analyses model plus migration plus RLS, backend/src/testpilot/ai_analysis/models.py (Req: data-model.md ai_analyses, FR-084) - depends on T073, T148
- [X] T159 [US5] [AI] Implement analyze_failure on the fake and cloud LLMProvider adapters, backend/src/testpilot/ai_provider/fake.py, backend/src/testpilot/ai_provider/cloud.py (Req: contracts/ai-provider-adapter.md) - depends on T111
- [X] T160 [US5] [AI] Implement the ai_analysis library: context assembly, step/expected/actual/log/screenshot reference, scoped strictly to the requester's Organization, backend/src/testpilot/ai_analysis/service.py (Req: FR-079 to FR-082, FR-086, SEC-012) - depends on T159, T152
- [X] T161 [US5] [Backend] Implement the analyze endpoint plus analysis-version list/get, backend/src/testpilot/api/v1/testruns.py (Req: contracts/test-runs-api.md) - depends on T160, T156
- [X] T162 [US5] [Backend] Implement the ai-analysis worker job handler, AnalyzeFailureJob, backend/src/testpilot/worker/jobs/analyze_failure.py (Req: contracts/worker-jobs.md) - depends on T160
- [X] T163 [US5] [Backend] Wire the ai_operations plan-limit check before enqueueing analysis, backend/src/testpilot/ai_analysis/service.py (Req: FR-123 to FR-125) - depends on T077, T160
- [X] T253 [US5] [AI] CLI: testpilot-cli ai analyze <result_id>, enqueues an analysis job and prints the ai_analysis id/status, wrapping ai_analysis directly, backend/src/testpilot/cli/ai.py (Req: constitution Principle II) - depends on T160, T163, T252, T249
- [X] T164 [US5] [Frontend] Build the AI analysis panel on the result detail page, explanation/root-cause/severity/fix plus expected-vs-actual, frontend/src/features/testruns/AIAnalysisPanel.tsx (Req: FR-081, FR-082) - depends on T154, T161
- [X] T165 [US5] [Frontend] Implement the request/re-request analysis action plus a distinct analysis-unavailable state, frontend/src/features/testruns/AIAnalysisPanel.tsx (Req: FR-083, FR-085) - depends on T164
- [X] T166 [US5] [Testing] E2E test: request analysis on a failed result and see the explanation, then force-fail the provider and see the distinct unavailable state, frontend/tests/e2e/ai-analysis.spec.ts (Req: quickstart.md Section 7) - depends on T165

**Checkpoint**: The full MVP core loop, sign up, create a project, generate tests, run them, get AI analysis on failures, is complete and independently demoable.

---

## Phase 14: Bug/Issue Management, User Story 7, Priority P2, MVP

**Goal**: Failed results and manual findings become tracked issues linked back to their source
test case and run.

**Independent Test**: Create an issue from a failed result (attachments and links copied
correctly), create one manually, move it through its status lifecycle, filter the issue list.

### Tests for User Story 7

- [X] T167 [P] [US7] [Testing] Contract test: issues CRUD, create-from-result, attachments, backend/tests/contract/test_issues.py (Req: contracts/issues-api.md)
- [X] T168 [US7] [Testing] Integration test: create-from-result copies attachments and the link survives an edit to the source test case, backend/tests/integration/test_issues_from_result.py (Req: FR-096)

### Implementation for User Story 7

- [X] T169 [US7] [DB] Create issues and issue_attachments models plus migration plus RLS, backend/src/testpilot/issues/models.py (Req: data-model.md issues) - depends on T073, T136
- [X] T170 [US7] [Backend] Implement the issues library: CRUD, status lifecycle, create-from-result copying attachment references, backend/src/testpilot/issues/service.py (Req: FR-087 to FR-096) - depends on T169
- [X] T171 [US7] [Backend] Implement issue routes, backend/src/testpilot/api/v1/issues.py (Req: contracts/issues-api.md) - depends on T170, T167
- [X] T172 [US7] [Frontend] Build the issues list page, filter by status and severity, frontend/src/app/(dashboard)/projects/[projectId]/issues/page.tsx (Req: FR-093) - depends on T029, T171
- [X] T173 [US7] [Frontend] Build the manual issue creation page, frontend/src/app/(dashboard)/projects/[projectId]/issues/new/page.tsx (Req: FR-088) - depends on T171
- [X] T174 [US7] [Frontend] Build the issue detail page, status transitions plus attachments, frontend/src/app/(dashboard)/projects/[projectId]/issues/[issueId]/page.tsx (Req: FR-089 to FR-092) - depends on T171
- [X] T175 [US7] [Frontend] Wire the create-issue-from-result action onto the result detail page, frontend/src/app/(dashboard)/projects/[projectId]/test-runs/[testRunId]/results/[testResultId]/page.tsx (Req: FR-087) - depends on T154, T171
- [X] T176 [US7] [Testing] E2E test: create an issue from a failed result, verify its links, move it through the status lifecycle, frontend/tests/e2e/issues.spec.ts (Req: quickstart.md Section 9) - depends on T172, T173, T174, T175

**Checkpoint**: Failures can now be triaged all the way to a tracked bug, closing the loop from Story 5's AI analysis.

---

## Phase 15: AI QA Assistant, User Story 10, Priority P3, Future — Scaffold Only

**Goal**: Reserve the interface and data model for the conversational assistant without building
its functionality, so it can be added later without a breaking change.

- [X] T177 [US10] [DB] Create assistant_conversations and assistant_messages models, Future schema per data-model.md, plus migration, backend/src/testpilot/assistant/models.py (Req: FR-097 to FR-103, Future Scope) - depends on T073
- [X] T178 [US10] [AI] Implement chat on the fake LLMProvider adapter, interface already reserved per contracts/ai-provider-adapter.md, backend/src/testpilot/ai_provider/fake.py (Req: contracts/ai-provider-adapter.md) - depends on T111
- [X] T179 [US10] [Backend] Implement a chat endpoint stub returning 501 not_implemented at MVP with the data model already in place, backend/src/testpilot/api/v1/assistant.py (Req: Future Scope) - depends on T177
- [X] T180 [US10] [Frontend] Build the AI QA Assistant page scaffold, chat UI shown as a coming-soon state at MVP, frontend/src/app/(dashboard)/assistant/page.tsx (Req: FR-023, Future Scope) - depends on T068
- [X] T181 [US10] [Testing] Test: the chat endpoint returns 501 without erroring the app, backend/tests/contract/test_assistant_stub.py (Req: Future Scope) - depends on T179

**Checkpoint**: The Future capability is visibly present in navigation and API surface but honestly non-functional, not silently missing.

---

## Phase 16: Reports and Analytics, User Story 8, Priority P2, MVP (basic) / Future (trend, rollup)

**Goal**: A project's testing health, totals, pass rate, coverage, issue severity, run history,
at a glance.

**Independent Test**: With a project that has completed runs (Story 4) and issues (Story 7),
open its report and verify every number matches the underlying data.

### Tests for User Story 8

- [X] T182 [P] [US8] [Testing] Contract test: reports summary/issues-by-severity/run-history endpoints match seeded data, backend/tests/contract/test_reports.py (Req: contracts/reports-api.md)
- [X] T183 [US8] [Testing] Integration test: coverage_percentage is computed correctly against approved-versus-executed cases, backend/tests/integration/test_reports_coverage.py (Req: FR-105)
- [X] T254 [P] [US8] [Testing] CLI test: testpilot-cli reports summary command, using Typer's CliRunner, backend/tests/unit/cli/test_reports_cli.py (Req: constitution Principle II) - depends on T184

### Implementation for User Story 8

- [X] T184 [US8] [Backend] Implement the reports library, on-read aggregation using test_runs summary counters, backend/src/testpilot/reports/service.py (Req: FR-104 to FR-107, FR-110) - depends on T136, T169
- [X] T185 [US8] [Backend] Implement reports routes, summary, issues-by-severity, run-history, backend/src/testpilot/api/v1/reports.py (Req: contracts/reports-api.md) - depends on T184, T182
- [X] T255 [US8] [Backend] CLI: testpilot-cli reports summary <project_id>, wrapping the reports library directly, human-readable and --json output, backend/src/testpilot/cli/reports.py (Req: constitution Principle II) - depends on T184, T254
- [X] T186 [US8] [Frontend] Build the project Reports page, StatCards plus severity chart plus run history table, frontend/src/app/(dashboard)/projects/[projectId]/reports/page.tsx (Req: FR-104 to FR-107, UX-009) - depends on T028, T185
- [X] T187 [US8] [Testing] E2E test: the Reports page totals match the runs and issues created in earlier E2E flows, frontend/tests/e2e/reports.spec.ts (Req: quickstart.md Section 10) - depends on T186
- [X] T188 [US8] [Backend] Implement a trend endpoint stub and an Organization-level rollup endpoint stub, both Future and returning 501, plus a code comment on T184's aggregation queries confirming the report-export data shape (FR-109) requires no redesign, backend/src/testpilot/api/v1/reports.py (Req: FR-108, FR-109, FR-111, Future Scope) - depends on T185

**Checkpoint**: Every MVP user story (1 through 8) is now independently functional; Reports gives visibility into everything built so far.

---

## Phase 17: Notifications, User Story 9, Priority P2, MVP

**Goal**: Users learn about run completions, critical failures, and AI analysis completion
without polling the dashboard manually.

**Independent Test**: Complete a run and an analysis (Stories 4 and 5), open the notification
center, verify one notification per event, correctly marked unread, deep-linking correctly.

### Tests for User Story 9

- [X] T189 [P] [US9] [Testing] Contract test: notifications list/read/read-all, backend/tests/contract/test_notifications.py (Req: contracts/notifications-api.md)

### Implementation for User Story 9

- [X] T190 [US9] [DB] Create notifications model plus migration plus RLS, backend/src/testpilot/notifications/models.py (Req: data-model.md notifications) - depends on T073
- [X] T191 [US9] [Backend] Implement the notifications library: create, list, mark-read, backend/src/testpilot/notifications/service.py (Req: FR-112 to FR-116) - depends on T190
- [X] T192 [US9] [Backend] Wire notification creation into the execute_test_run and analyze_failure worker jobs, run_completed, run_failed_critical, ai_analysis_completed, ai_analysis_failed, backend/src/testpilot/worker/jobs/execute_test_run.py, backend/src/testpilot/worker/jobs/analyze_failure.py (Req: FR-112 to FR-114) - depends on T141, T162, T191
- [X] T193 [US9] [Backend] Implement notifications routes, backend/src/testpilot/api/v1/notifications.py (Req: contracts/notifications-api.md) - depends on T191, T189
- [X] T194 [US9] [Frontend] Wire the NotificationBell component from Phase 5 to real data, unread count, list, mark-read, frontend/src/components/layout/NotificationBell.tsx (Req: FR-115, FR-116) - depends on T071, T193
- [X] T195 [US9] [Frontend] Build the full notifications page, frontend/src/app/(dashboard)/notifications/page.tsx (Req: FR-115) - depends on T193
- [X] T196 [US9] [Testing] E2E test: completing a run and an analysis produces notifications that deep-link to the correct run/result, frontend/tests/e2e/notifications.spec.ts (Req: quickstart.md Section 11) - depends on T194, T195

**Checkpoint**: All 9 MVP-relevant user stories (1 to 9) plus the Future-scaffolded 10 and 11 are complete. Story 12 (subscription architecture) was already delivered incrementally in Phase 6.

---

## Phase 18: API Layer Hardening (Cross-Cutting)

**Purpose**: Consolidate and harden the API surface every feature phase already built
incrementally, per this file's build-order note.

- [X] T197 [Backend] Add a pagination helper and apply it consistently across every list endpoint, backend/src/testpilot/api/pagination.py (Req: contracts/_conventions.md) - depends on T091, T102, T140, T171
- [X] T198 [Backend] Audit and normalize error-envelope codes across every endpoint against contracts/*.md, backend/src/testpilot/core/exceptions.py (Req: plan.md Error Handling) - depends on all Phase 4-17 backend endpoint tasks
- [X] T199 [Backend] Wire slowapi rate limiting on the AI generation/analysis and test-execution-trigger endpoints, the SEC-009 remainder beyond auth, backend/src/testpilot/api/deps.py (Req: SEC-009, FR-132) - depends on T117, T140, T161
- [X] T200 [DevOps] Generate and validate an OpenAPI schema against contracts/*.md and publish it as a build artifact, backend/scripts/export_openapi.py (Req: plan.md API Design) - depends on T198
- [X] T201 [Testing] Contract-coverage audit: verify every contracts/*.md endpoint has a passing contract test, backend/tests/contract/test_contract_coverage.py (Req: constitution Integration Testing) - depends on T200

**Checkpoint**: The API surface is internally consistent and fully covered by contract tests.

---

## Phase 19: Database and Migrations Hardening (Cross-Cutting)

**Purpose**: Full audit of tenant isolation and index coverage across the schema built
incrementally in every feature phase.

- [X] T202 [DB] Full RLS policy audit: confirm every tenant table listed in data-model.md has a policy applied, backend/alembic/versions/xxxx_rls_audit.py (Req: DATA-001, SEC-011) - depends on T073, T190
- [X] T203 [DB] Add and verify every index listed in data-model.md, composite, GIN, and unique, across all migrations, backend/alembic/versions/xxxx_indexes_audit.py (Req: data-model.md indexes) - depends on T202
- [X] T204 [DB] Add an Alembic CI check confirming migrations apply cleanly to a fresh database with no drift, backend/scripts/check_migrations.py (Req: constitution Technology & Quality Constraints) - depends on T203
- [X] T205 [DB] Write a subscription_plans and reference-data seed script, kept separate from migrations, backend/scripts/seed_reference_data.py (Req: FR-122) - depends on T041

**Checkpoint**: Tenant isolation and query performance are provably correct across the entire schema, not just the tables each feature phase happened to test.

---

## Phase 20: Security and Validation Hardening (Cross-Cutting)

**Purpose**: A dedicated security pass across everything built in Phases 4 through 17, matching
spec.md's Security Requirements section item by item.

- [X] T206 [Backend] Security review pass: confirm every write endpoint validates via SQLModel/Pydantic request models with no raw dict handling, and spot-check injection/XSS/CSRF/IDOR protections per FR-134, backend/src/testpilot/api/v1/ (Req: SEC-007, FR-130, FR-134) - depends on all Phase 4-17 endpoint tasks
- [X] T207 [Backend] Confirm the SSRF guard is invoked at both project-creation and execution time with no bypass path, backend/src/testpilot/execution/engine.py, backend/src/testpilot/projects/service.py (Req: SEC-006, FR-035, FR-135) - depends on T089, T130
- [X] T208 [P] [DevOps] Add a dependency vulnerability scan to CI, pip-audit and npm audit, .github/workflows/ci.yml (Req: plan.md Security Architecture)
- [X] T209 [Backend] Confirm audit-log coverage for every SEC-010-listed event type, deletions and permission changes, across all libraries, backend/src/testpilot/audit/service.py (Req: SEC-010, FR-128 to FR-129) - depends on T057, T090, T170
- [X] T210 [Testing] Security-focused test pass: confirm cross-tenant access returns 404, never 403, across every resource type, backend/tests/integration/test_tenant_isolation_full.py (Req: FR-136, SEC-011) - depends on T080

**Checkpoint**: Every Security Requirement in spec.md (SEC-001 through SEC-013) has a corresponding verification, not just an architectural claim.

---

## Phase 21: Automated Testing Infrastructure (Cross-Cutting)

**Purpose**: The test-runner configuration every earlier phase's test tasks assumed already
existed; formalized here so CI is reproducible.

- [X] T211 [DevOps] Configure the pytest plus pytest-asyncio plus httpx ASGI test harness, backend/pyproject.toml, backend/tests/conftest.py (Req: research.md #14) - depends on T002
- [X] T212 [DevOps] Configure ephemeral Postgres plus Redis test fixtures, testcontainers or CI service containers, backend/tests/conftest.py (Req: research.md #14) - depends on T211
- [X] T213 [DevOps] Configure Playwright Test for frontend E2E, frontend/playwright.config.ts (Req: research.md #14) - depends on T003
- [X] T214 [Testing] Add an eslint-plugin-jsx-a11y CI gate that fails the build on accessibility lint errors, .github/workflows/ci.yml (Req: NFR-013, NFR-014) - depends on T005
- [X] T215 [Testing] Wire a backend unit-test coverage report into CI, backend/pyproject.toml (Req: constitution Test-First) - depends on T211

**Checkpoint**: Every test task from Phases 4-20 can actually run in CI, not just locally.

---

## Phase 22: Performance and Observability (Cross-Cutting)

**Purpose**: Structured logging, metrics, and error tracking across the API and worker
processes, per NFR-009 to NFR-012.

- [X] T216 [Backend] Implement structured JSON logging with correlation_id, organization_id, and user_id fields, backend/src/testpilot/core/logging.py (Req: NFR-009, FR-138) - depends on T011
- [X] T217 [Backend] Wire correlation_id propagation from the API request into the worker job envelope, backend/src/testpilot/worker/main.py (Req: contracts/worker-jobs.md envelope) - depends on T216, T118
- [X] T218 [Backend] Add a Prometheus metrics endpoint plus queue-depth, job-duration, and error-rate counters, backend/src/testpilot/api/v1/health.py, backend/src/testpilot/worker/main.py (Req: NFR-011, FR-138) - depends on T012
- [X] T219 [Backend] Wire the Sentry SDK on both the API and worker processes, backend/src/testpilot/core/observability.py (Req: NFR-012) - depends on T011
- [X] T220 [Backend] Add a Redis caching helper for org plan/limits and project metadata reads, with explicit invalidation on write, backend/src/testpilot/core/cache.py (Req: NFR-008) - depends on T077, T090

**Checkpoint**: The system is debuggable in production from logs, metrics, and error tracking alone, per the constitution's Observability principle.

---

## Phase 23: Docker and Local Deployment (Cross-Cutting)

**Purpose**: A one-command local stack matching quickstart.md's prerequisites.

- [X] T221 [DevOps] Write backend.Dockerfile, shared base image for api and worker with CMD override, infra/docker/backend.Dockerfile (Req: research.md #16) - depends on T002
- [X] T222 [DevOps] Write frontend.Dockerfile, multi-stage Next.js production build, infra/docker/frontend.Dockerfile (Req: research.md #16) - depends on T003
- [X] T223 [DevOps] Write docker-compose.yml, postgres, redis, minio, api, worker, frontend, infra/docker/docker-compose.yml (Req: research.md #16) - depends on T221, T222
- [X] T224 [DevOps] Write a MinIO bucket-init script for local artifact storage, infra/docker/minio-init.sh (Req: research.md #8) - depends on T150
- [X] T225 [Testing] Validate quickstart.md Sections 1 and 2 (stack boots, migrations apply) against the docker-compose stack, results recorded in specs/001-testpilot-ai-platform/quickstart-results.md (Req: quickstart.md Sections 1-2) - depends on T223, T009

**Checkpoint**: `docker compose up` reproduces quickstart.md's expected running services from a clean checkout.

---

## Phase 24: CI/CD (Cross-Cutting)

**Purpose**: The staged pipeline described in plan.md and research.md #15.

- [X] T226 [DevOps] GitHub Actions stage 1: lint, type-check, and unit tests on every push, .github/workflows/ci.yml (Req: research.md #15) - depends on T004, T005, T211
- [X] T227 [DevOps] GitHub Actions stage 2: integration and contract tests against ephemeral Postgres plus Redis service containers, .github/workflows/ci.yml (Req: research.md #15) - depends on T212, T226
- [X] T228 [DevOps] GitHub Actions stage 3: build and push versioned api, worker, and frontend images on merge to main, .github/workflows/ci.yml (Req: research.md #15) - depends on T221, T222, T227

**Checkpoint**: Every push gets fast lint/unit feedback; every merge to main produces deployable images.

---

## Phase 25: Kubernetes Readiness (Cross-Cutting)

**Purpose**: The documented manifest shape from plan.md's Kubernetes-Readiness section, made
concrete (still not deployed anywhere as part of this task list).

- [X] T229 [DevOps] Write base Deployment manifests for api, worker, and frontend with independent replica counts, infra/k8s/base/deployments.yaml (Req: NFR-005) - depends on T221, T222
- [X] T230 [DevOps] Write Service and Ingress manifests for api and frontend, infra/k8s/base/service-ingress.yaml (Req: plan.md Kubernetes-Readiness) - depends on T229
- [X] T231 [DevOps] Write ConfigMap and Secret templates for non-secret config and credentials, infra/k8s/base/config.yaml (Req: SEC-004) - depends on T006
- [X] T232 [DevOps] Wire liveness and readiness probes to /healthz and /readyz in the Deployment manifests, infra/k8s/base/deployments.yaml (Req: NFR-010) - depends on T012, T229
- [X] T233 [Docs] Document the Future HPA/KEDA queue-depth autoscaling hook, not implemented in this phase, infra/k8s/README.md (Req: plan.md Kubernetes-Readiness) - depends on T229

**Checkpoint**: The manifest set is complete enough to apply to a real cluster when deployment is actually scheduled, without further design work.

---

## Phase 26: Final Integration, QA, and Release Preparation (Cross-Cutting)

**Purpose**: Prove the whole system together against quickstart.md, not just each phase in
isolation, and leave the codebase in a release-ready state.

- [X] T234 [Testing] Execute quickstart.md Sections 3 through 11 end-to-end against the docker-compose stack, every MVP user story in one continuous run, results recorded in specs/001-testpilot-ai-platform/quickstart-results.md (Req: quickstart.md Sections 3-11) - depends on all Phase 4-17 implementation tasks
- [X] T235 [Testing] Execute quickstart.md Section 12, tenant-isolation validation with two real accounts, results recorded in specs/001-testpilot-ai-platform/quickstart-results.md (Req: quickstart.md Section 12, SEC-011) - depends on T210
- [X] T236 [Testing] Execute quickstart.md Section 13, plan-limit validation via the CLI, results recorded in specs/001-testpilot-ai-platform/quickstart-results.md (Req: quickstart.md Section 13, FR-123) - depends on T077, T090, T243, T238
- [X] T237 [Testing] Execute quickstart.md Section 14, accessibility and responsive spot-check, keyboard-only plus mobile viewport, results recorded in specs/001-testpilot-ai-platform/quickstart-results.md (Req: quickstart.md Section 14, NFR-013 to NFR-015) - depends on all Phase 2-17 frontend tasks
- [X] T238 [Backend] Implement the testpilot-cli Typer app entrypoint (backend/src/testpilot/cli/main.py) and register the per-domain subcommand groups built incrementally in Phases 6, 7, 8, 9, 11, 13, and 16 (billing, projects, testcases, ai, run, reports) into one distributable CLI, per the constitution's CLI Interface principle. This is a final assembly/wiring step over already-built and already-tested commands, not the first place any command's logic is implemented — see T243, T245, T247, T249, T251, T253, T255 for where each domain's CLI logic actually lives, next to its corresponding feature phase, backend/src/testpilot/cli/main.py (Req: constitution Principle II) - depends on T243, T245, T247, T249, T251, T253, T255
- [X] T239 [Testing] Full regression pass: re-run every phase's E2E suite together against one running stack, results recorded in specs/001-testpilot-ai-platform/quickstart-results.md (Req: constitution Test-First) - depends on T234
- [X] T240 [Docs] Write a release checklist/runbook: deploy steps, rollback, and known Future-scope gaps, docs/RELEASE.md (Req: constitution Development Workflow) - depends on T239

**Checkpoint**: The MVP (spec.md's MVP Scope, all of it) is proven working end-to-end in one sitting, and the repository is in a state a new contributor or reviewer could pick up from the README plus this checklist.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies, can start immediately.
- **Design System (Phase 2)**: Depends on Phase 1 (frontend project must exist). Blocks every page-building task in Phases 3-17.
- **Landing Page (Phase 3)**: Depends on Phase 2 (T033 SidebarNav/Topbar are reused patterns; marketing layout is independent of the dashboard shell itself).
- **Authentication (Phase 4, US1)**: Depends on Phases 1-2. Blocks every other feature phase — every later phase's routes require `current_user`/`current_organization` (T054) and every later page requires the auth guard (T064).
- **Dashboard Shell (Phase 5)**: Depends on Phase 4 (T064). Blocks every authenticated page in Phases 6-17.
- **Organizations/Permissions (Phase 6)**: Depends on Phase 5. Extends the RLS pattern (T043) that Phases 7-17's DB tasks all depend on (T073).
- **Project Management (Phase 7, US2)**: Depends on Phase 6 (T073 RLS pattern, T077 billing check).
- **Test Case Management (Phase 8, US6)**: Depends on Phase 7 (T088 projects model).
- **AI Generation (Phase 9, US3)**: Depends on Phase 8 (T100 test_cases model) AND Phase 10's T125/T126 (see the build-order note at the top of this file) — plan accordingly if executing phases strictly in order.
- **Playwright Engine (Phase 10)**: Depends on Phase 1 only (T125/T126 have no feature-phase dependency); build it in parallel with or before Phase 9 despite its later phase number.
- **Test Execution (Phase 11, US4)**: Depends on Phase 8 (test cases to select) and Phase 10 (engine).
- **Test Results (Phase 12)**: Depends on Phase 11 (T136 test_runs/test_results models).
- **AI Failure Analysis (Phase 13, US5)**: Depends on Phase 12 (T148 artifacts, T152 result detail).
- **Bug/Issue Management (Phase 14, US7)**: Depends on Phase 11 (T136 test_runs/test_results — issues can originate from results).
- **AI QA Assistant (Phase 15, US10, Future)**: Depends only on Phase 6 (T073 RLS pattern); can be built any time after, position in the list is thematic, not a hard dependency on Phases 7-14.
- **Reports (Phase 16, US8)**: Depends on Phase 11 (T136 summary counters) and Phase 14 (T169 issues).
- **Notifications (Phase 17, US9)**: Depends on Phase 11 (T141 execute_test_run job) and Phase 13 (T162 analyze_failure job).
- **Phases 18-22 (API/DB/Security/Testing/Observability hardening)**: Each depends on the feature phases whose output it hardens (see each phase's task-level `depends on`); they are audit/consolidation passes, not first-touch work, so they are ordered last on purpose even though some of their groundwork (e.g., T211 pytest config) is referenced by test tasks throughout Phases 4-17 — those referencing test tasks assume a working pytest setup exists in practice from Phase 1 onward, formalized fully by Phase 21.
- **Phases 23-25 (Docker/CI-CD/Kubernetes)**: Depend on Phase 1 (T002/T003) and, for CI's integration stage, Phase 21.
- **Phase 26 (Final integration)**: Depends on every MVP feature phase (4, 7-14, 16-17) being complete.

### User Story Dependencies

- **US1 (Auth, P1)**: No dependency on other stories. The true foundation.
- **US2 (Projects, P1)**: Depends on US1 (needs an authenticated org).
- **US6 (Test Case Library, P2)**: Depends on US2 (needs a project).
- **US3 (AI Generation, P1)**: Depends on US6 (needs the test_cases model) and the Phase 10 engine.
- **US4 (Test Execution, P1)**: Depends on US6 (cases to run) and the Phase 10 engine.
- **US5 (AI Failure Analysis, P1)**: Depends on US4 (needs a failed result to analyze).
- **US7 (Issues, P2)**: Depends on US4 (can originate from a result) but also independently usable for manual issues once US2 exists.
- **US8 (Reports, P2)**: Depends on US4 (test run data) and US7 (issue data).
- **US9 (Notifications, P2)**: Depends on US4 and US5 (the events it notifies about).
- **US10 (AI Assistant, P3, Future)**: Depends only on US1 (org context); scaffold-only in this task list.
- **US11 (Multi-member Orgs, P3, Future)**: Depends only on US1; scaffold-only in this task list.
- **US12 (Subscription Architecture, P3)**: Delivered incrementally inside Phase 6 (billing) rather than as its own phase, since spec.md frames it as cross-cutting architecture, not a standalone user flow.

### Within Each Phase

- Tests are written and confirmed failing before their corresponding implementation task, per the constitution's Test-First principle (NON-NEGOTIABLE) — this is not optional here even though the tasks-template.md marks tests as optional by default.
- Models before services; services before routes; routes before frontend pages that call them.
- Each phase's Checkpoint must pass before the next MVP-priority phase is considered done, even if work on a later phase has started in parallel.

### Parallel Opportunities

- All tasks marked [P] within a phase touch different files and can be built simultaneously.
- Once Phase 6 completes, Phases 7 (Projects) and 15 (AI Assistant scaffold) have no dependency on each other and could be staffed in parallel.
- Phase 10 (Playwright engine) has no dependency on Phases 7-9 and can be built in parallel with them from Phase 1 onward — doing so removes the Phase 9/Phase 10 ordering wrinkle entirely.
- Phases 18-22 (hardening) can each be staffed in parallel once their respective feature phases land, rather than waiting for all of Phases 4-17 to finish first.

---

## Parallel Example: User Story 1 (Phase 4)

```
# Launch these test tasks together (different files, no shared dependency):
Task: "Contract test: POST /auth/signup - backend/tests/contract/test_auth_signup.py"
Task: "Contract test: POST /auth/login, POST /auth/logout, POST /auth/refresh - backend/tests/contract/test_auth_login.py"
Task: "Contract test: POST /auth/forgot-password, POST /auth/reset-password - backend/tests/contract/test_auth_password_reset.py"

# Launch these model tasks together (different files):
Task: "Create organizations, memberships, subscription_plans models - backend/src/testpilot/orgs/models.py"
Task: "Create users, refresh_tokens, password_reset_tokens models - backend/src/testpilot/auth/models.py"

# Launch these utility tasks together (different files, no shared dependency):
Task: "Implement Argon2id password hashing utilities - backend/src/testpilot/auth/security.py"
Task: "Implement JWT access-token sign/verify utilities - backend/src/testpilot/auth/tokens.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only, then incrementally)

1. Complete Phase 1 (Setup) and Phase 2 (Design System) — nothing else can start without these.
2. Complete Phase 4 (User Story 1, Authentication) plus Phase 5 (Dashboard Shell) plus Phase 6 (Organizations/tenancy hardening) — this is the true "Foundational" block for a multi-tenant SaaS, even though it spans three named phases.
3. **STOP and VALIDATE**: run quickstart.md Section 3 independently.
4. Add Phase 7 (Projects, US2) → validate quickstart.md Section 4.
5. Add Phase 10 (Playwright engine) in parallel with Phase 8 (Test Case Library, US6) → validate quickstart.md Section 8.
6. Add Phase 9 (AI Generation, US3) → validate quickstart.md Section 5. **This is the first point the product's core AI differentiator is demoable.**
7. Add Phase 11 (Test Execution, US4) plus Phase 12 (Results/Screenshots) → validate quickstart.md Section 6. **This is MVP-critical mass: URL → AI test cases → real browser execution → results.**
8. Add Phase 13 (AI Failure Analysis, US5) → validate quickstart.md Section 7. **The second core AI differentiator; the product's full core loop is now demoable end-to-end.**
9. Add Phase 14 (Issues, US7) → validate quickstart.md Section 9.
10. Add Phase 16 (Reports, US8) → validate quickstart.md Section 10.
11. Add Phase 17 (Notifications, US9) → validate quickstart.md Section 11.
12. Add Phase 15 (AI Assistant scaffold, US10, Future) — no functional validation, coming-soon state only.
13. Run Phases 18-22 (hardening passes) against everything built so far.
14. Run Phases 23-25 (Docker, CI/CD, Kubernetes manifests).
15. Run Phase 26 (final integration) as the release gate.

### Incremental Delivery Checkpoints

Every "validate quickstart.md Section N" step above is a real stop-and-demo point — each adds
user-visible value without breaking anything validated in a previous step, satisfying the
Task Generation Rules' independent-testability requirement even though this product's stories
have more real sequential dependency (auth → projects → test cases → generation → execution →
analysis) than a typical three-independent-story example, because that dependency chain is the
literal shape of the product itself (spec.md's own User Story numbering already reflects it).

### Parallel Team Strategy

With multiple developers, once Phase 6 completes:
- One developer: Phase 10 (Playwright engine, no dependency on Phases 7-9).
- One developer: Phase 7 → Phase 8 → Phase 9 (Projects → Test Cases → AI Generation, the critical path).
- One developer: Phase 2's remaining design-system polish plus Phase 3 (Landing) plus Phase 15 (AI Assistant scaffold).
- Once Phase 9 and Phase 10 both land, converge on Phase 11 (Execution) together.

---

## Notes

- [P] tasks touch different files with no unmet dependency.
- [Story] labels map every feature-phase task to its spec.md user story for traceability; Setup, Foundational, and cross-cutting phases (1, 2, 5, 10, 18-26) intentionally carry no [Story] label per the format rules.
- Every task's `(Req: ...)` citation is the acceptance criterion for that task — a task is "done" when the cited requirement, contract, or quickstart.md section it implements actually holds, not merely when code compiles.
- Tests are mandatory here, not optional, per the constitution's Test-First (NON-NEGOTIABLE) principle — write the test, confirm it fails, then implement.
- Commit after each task or logical group, per repository convention.
- Stop at any Checkpoint to validate a story independently before continuing.
- Total: 255 tasks across 26 phases. MVP-critical path (Phases 1-14, 16-26, excluding the explicitly Future-labeled Phase 15 and the Future-labeled tasks within Phases 6 and 16): the vast majority of the 255 — only T083, T084 (Phase 6), T177-T181 (Phase 15), and T188 (Phase 16) are Future-scope/scaffold-only tasks; every other task is MVP, including all 14 CLI tasks (T242-T255) distributed per-domain per the constitution's CLI Interface principle (see the build-order note near the top of this file).
- **Post-analysis remediation record**: T241 (account-deletion endpoint, DATA-004) and T242-T255 (14 distributed per-domain CLI tasks) were added after a `/speckit-analyze` pass found a real coverage gap and a constitution-sequencing issue respectively. T238 itself was not removed — it was revised in place (same ID, scope narrowed from "implement every CLI command" to "assemble the already-built commands into one entrypoint"), so no previously-valid task was deleted; its dependencies were updated to point at the new distributed tasks instead of raw library modules.
- **Requirement-coverage note**: every spec.md functional requirement is either cited directly by a task's `(Req: ...)` tag, covered by a range citation (e.g., "FR-041 to FR-044"), or is one of the following Future-scope "must not preclude a later redesign" requirements that this task list satisfies through architectural choice rather than a dedicated buildable task: FR-034 (project tagging — precluded by nothing in the projects schema, T088), FR-048 (authenticated-flow analysis — precluded by nothing in T125's interface-based engine), FR-058 (bulk test-case operations — precluded by nothing in T101's service layer), FR-077 (parallel execution — precluded by nothing in T137's per-case orchestration loop), FR-078 (run cancellation — precluded by nothing in T136's status enum), FR-117 (notification channels beyond in-app — precluded by nothing in T190's notification schema), FR-118 (per-user notification preferences — precluded by nothing in T190's notification schema), FR-011 (additional auth methods such as SSO/OAuth — precluded by nothing in T042/T049's session model). None of these eight require code today; they require that today's code not paint the project into a corner, which the cited MVP tasks already ensure. The same logic covers INT-005, INT-006, and INT-007 (payment gateway, CI/CD webhook triggers, chat-platform notifications — all explicitly Future Scope) and SEC-005 (the MVP satisfies "never store site-under-test credentials" by simply never building that capability anywhere in this task list, not by a task that enforces an absence).
- **Non-functional / success-criteria validation note**: NFR-001 to NFR-003 (dashboard/report/run-trigger latency targets) and every SC-001 to SC-010 success criterion are outcome-level measurements, not individually buildable tasks — they are what Phase 26's quickstart execution (T234-T239) validates the finished system against, per quickstart.md's own structure. If any measurement fails during Phase 26, the fix is a task added to the relevant earlier phase, not a new Phase 26 task.

