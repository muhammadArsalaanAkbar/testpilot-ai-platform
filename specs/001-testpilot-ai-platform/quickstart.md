# Quickstart: TestPilot AI

**Feature**: `001-testpilot-ai-platform` | **Date**: 2026-08-05

This is a validation/run guide, not an implementation guide. It documents how a working build of
this plan is expected to be brought up locally and how to prove each MVP user story (spec.md)
actually works end-to-end. It does not contain model/service/controller code, migrations, or
test suites — those are implementation-phase artifacts driven by `tasks.md`.

## Prerequisites

- Docker + Docker Compose (runs Postgres, Redis, MinIO, and all three deployables together)
- Node.js 20 LTS + npm (frontend, if running outside its container for faster iteration)
- Python 3.12 + `uv` (backend, if running outside its container for faster iteration)
- A cloud LLM provider API key for the configured `AI_PROVIDER` (see `research.md` #7) — a
  local/mock provider mode is expected to exist for running the suite without a real key (used
  in CI and for the "AI unavailable" edge-case validation below)

## 1. Bring up the stack

```
cp infra/docker/.env.example infra/docker/.env   # fill in AI provider key, JWT secret, etc.
docker compose -f infra/docker/docker-compose.yml up
```

Expected running services: `postgres`, `redis`, `minio`, `api` (FastAPI on its configured port),
`worker` (one process per queue, per plan.md), `frontend` (Next.js dev/prod server).

**Validate**: `GET /api/v1/healthz` returns `200`; `GET /api/v1/readyz` returns `200` once
Postgres/Redis are reachable (NFR-010). The frontend's landing page loads at its configured URL.

## 2. Database migrations

Alembic migrations apply automatically on `api`/`worker` container start in the dev compose
file. To run them manually against a running Postgres:

```
cd backend && uv run alembic upgrade head
```

**Validate**: all tables from `data-model.md` exist; `subscription_plans` is seeded with
Free/Starter/Professional/Enterprise rows (a seed script/fixture, not a migration, per standard
practice for reference data).

## 3. Story 1 — Sign up and manage an account

1. Open the frontend, go to `/signup`, submit a valid email/password.
2. **Expect**: redirected to `/overview` in a logged-in state; `GET /api/v1/auth/me` returns the
   new user and their auto-created personal Organization (FR-012).
3. Log out (`/settings/security` or topbar) → protected routes redirect to `/login`.
4. Log back in with the same credentials → back at `/overview`.
5. Use "forgot password" with the same email → check the configured local mail catcher (e.g.
   Mailhog, wired per `INT-003`) for the reset link → set a new password → log in with the new
   password only (old password now rejected).

**Contract reference**: `contracts/auth-api.md`.

## 4. Story 2 — Create a project

1. From `/overview` (empty state), click through to `/projects/new`.
2. Submit a name and a real, publicly reachable test URL (e.g. a demo site you control).
3. **Expect**: `201` from `POST /projects`; project appears at `/projects` with status `active`.
4. Submit a project with a URL resolving to `127.0.0.1` or a private IP range.
5. **Expect**: rejected with `422 url_not_public` (FR-035/SEC-006) — this specifically validates
   the SSRF guard, not just URL well-formedness.

**Contract reference**: `contracts/projects-api.md`.

## 5. Story 3 — Generate AI test cases

1. From the project detail page, trigger `/test-cases/generate`.
2. **Expect**: `202` with a `generation_run` in `queued` status; frontend polls
   `GET .../generate/{id}` until `completed`.
3. **Expect**: resulting test cases include a mix of `positive`/`negative`/`edge_case` flow
   types (FR-039/FR-040) and each has a non-empty `description` explaining its purpose (FR-038).
4. Edit one field of a generated case, approve two cases, reject one.
5. **Expect**: rejected case is excluded from selection when starting a test run (FR-057) but
   still visible in the library with `status=rejected`, not deleted (FR-042).
6. Trigger generation again immediately (before the first completes, if timing allows) or
   trigger `regenerate` on a case while a full-batch job is still running.
7. **Expect**: `409 generation_in_progress` (FR-047).

**Contract reference**: `contracts/test-cases-api.md`.

## 6. Story 4 — Execute a test run

1. Select the approved test cases from Story 3; start a test run.
2. **Expect**: `202`, run status moves `queued → running → completed`; frontend shows a live
   progress indicator (UX-004) that updates without a manual page refresh (polling, per
   `research.md` #11).
3. Open a completed result: **expect** an execution log and, for a failing case, at least one
   screenshot resolvable via a signed URL (FR-064/FR-072).
4. Retry only the failed tests from this run.
5. **Expect**: a new test run containing only the previously-failed case IDs; the original run's
   passed results are unchanged (FR-073).

**Contract reference**: `contracts/test-runs-api.md`, `contracts/browser-automation-adapter.md`.

## 7. Story 5 — AI failure analysis

1. On a failed result from Story 4, request AI analysis.
2. **Expect**: `202`, then a completed analysis containing explanation, root cause, severity,
   and suggested fix (FR-081), with the expected-vs-actual comparison explicitly shown
   (FR-082).
3. Re-request analysis on the same result.
4. **Expect**: a second `ai_analyses` row is created (history preserved, FR-085), not an
   overwrite of the first.
5. **Failure-path validation**: temporarily point `AI_PROVIDER` at the mock/unavailable provider
   mode and repeat step 1.
6. **Expect**: analysis resource reaches `status=failed` with a `failure_reason`, and the
   frontend shows a distinct "analysis unavailable" state (FR-083) — not a fabricated result and
   not the same UI as "no analysis requested."

**Contract reference**: `contracts/test-runs-api.md` (analysis endpoints),
`contracts/ai-provider-adapter.md`, `contracts/worker-jobs.md`.

## 8. Story 6 — Test case library management

1. With 10+ test cases in a project (from Stories 3/5 combined or additional manual cases),
   use the library's search box, then each filter (priority/severity/status/tag/source).
2. **Expect**: results narrow correctly for each filter independently and in combination
   (FR-050/FR-051).
3. Create a manual test case with the same field set as an AI-generated one.
4. **Expect**: appears with `source=manual`, fully editable (FR-053).

## 9. Story 7 — Bug/issue tracking

1. From a failed result (Story 4), create an issue.
2. **Expect**: issue pre-filled with title/description, the failure's screenshot/log attached,
   and links back to the source test case and test run (FR-087, FR-091).
3. Change its status through the lifecycle (`open → in_progress → resolved`).
4. Filter the issues list by status and by severity.

**Contract reference**: `contracts/issues-api.md`.

## 10. Story 8 — Reports

1. With at least two completed test runs and one issue in a project, open `/reports`.
2. **Expect**: total/passed/failed/skipped counts and pass percentage match what Stories 4/5
   actually produced; issue severity breakdown matches Story 7's issue(s); run history lists
   both runs (FR-104–FR-107).

**Contract reference**: `contracts/reports-api.md`.

## 11. Story 9 — Notifications

1. After a test run completes (Story 4) and an AI analysis completes (Story 5), open the
   notification center.
2. **Expect**: one notification per completed run and one per completed analysis, correctly
   marked unread; clicking one navigates directly to the relevant run/result (FR-114, FR-116,
   FR-117).
3. Force a run containing a critical-severity result (e.g. via a project/site known to fail
   critically, or a seeded fixture in a lower environment).
4. **Expect**: an additional distinctly-typed `run_failed_critical` notification (FR-115).

**Contract reference**: `contracts/notifications-api.md`.

## 12. Tenant isolation validation (SEC-011/DATA-001 — not a user story, but a required gate)

1. Sign up a second, independent account (second Organization).
2. From the second account's session, attempt `GET /projects/{id}` using a project ID that
   belongs to the first Organization (copy it from Story 2/4's browser network tab or API
   response).
3. **Expect**: `404 not_found` — indistinguishable from a nonexistent ID, never a `403` (FR-138).
   Repeat against a test run ID and an issue ID from the first account for the same result.

## 13. Plan-limit validation (FR-121–FR-127)

1. Using a test/admin path (e.g. the `testpilot-cli billing set-plan <org_id> free
   --max-projects=1`, per the CLI exposed in plan.md's Constitution Check), set an Organization's
   plan to a project limit of 1.
2. Attempt to create a second project.
3. **Expect**: `402 plan_limit_exceeded` naming the `projects` limit (FR-125), and the project is
   not created.

## 14. Accessibility/responsive spot-check (NFR-013–NFR-015)

1. Using keyboard only (no mouse), complete the Story 1 → Story 4 flow end-to-end.
2. **Expect**: every interactive element is reachable and operable via keyboard, with visible
   focus indication throughout.
3. Resize the browser to a mobile viewport width and repeat the Story 4 run-monitor and Story 6
   library-filter flows.
4. **Expect**: both remain fully usable (not just visible) at mobile width, per NFR-015.

## Done criteria for this quickstart

All 14 sections above pass against a single running stack brought up with the commands in
Section 1, using only the contracts in `contracts/` and the schema in `data-model.md` — no step
above should require reading application source code to know what to expect.
