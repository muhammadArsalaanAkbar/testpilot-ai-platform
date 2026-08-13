# Quickstart Validation Results

**Feature**: `001-testpilot-ai-platform` | **Validated**: 2026-08-12 (Sections 1-2), 2026-08-13
(Sections 3-14, Phase 26 Final Integration/QA), 2026-08-13–14 (CI/CD pipeline, post-Phase 26)

Results are recorded per quickstart.md section as each is validated against a real running
stack (not simulated/mocked). Sections not yet exercised are omitted rather than marked
speculatively pass/fail.

## Section 1 — Bring up the stack

**Method**: `docker compose -f infra/docker/docker-compose.yml up -d` from a clean build
(`docker compose build` with no cache reuse beyond normal layer caching), against
`infra/docker/.env` copied verbatim from `.env.example` with no value changes.

| Check | Result |
|---|---|
| All 7 services (`postgres`, `redis`, `minio`, `mailhog`, `api`, `worker`, `frontend`) reach a running state | PASS — `docker compose ps` showed `postgres`/`redis`/`minio`/`api` as `healthy`; `mailhog`/`frontend`/`worker` have no healthcheck defined and reported `running` |
| `GET /api/v1/healthz` returns 200 | PASS — `{"status":"ok"}` |
| `GET /api/v1/readyz` returns 200 once Postgres/Redis are reachable | PASS — `{"status":"ok","checks":{"database":"ok","redis":"ok"}}` |
| Frontend landing page loads at its configured URL | PASS — `GET http://localhost:3200/` returned 200 with the real rendered `<title>TestPilot AI — AI-Powered Web Application Testing</title>` page |
| `worker` container starts cleanly, listening on all three queues | PASS — worker logs show `*** Listening on ai-generation, test-execution, ai-analysis...` with no errors |
| `minio-init` one-shot service creates the artifact bucket | PASS — logs show `created bucket 'testpilot-artifacts'`; independently confirmed via `mc ls` against the running `minio` service |

**Startup ordering observed**: `postgres`/`redis`/`minio` became healthy first; `minio-init` ran
to completion; `api` started, ran its migrations, and became healthy; only then did `worker`
start (by design — `worker` depends on `api`'s healthcheck specifically so its own
`alembic upgrade head`, per Section 2, never races `api`'s, since both containers run
migrations at startup and RQ's own idempotent-header-check pattern doesn't extend to Alembic's
DDL).

**Note (not a failure, but a known limitation surfaced during validation)**: `docker compose ps`
prints `WARNING: The "APP_DB_PASSWORD" variable is not set. Defaulting to a blank string.` even
though `.env` defines it. Verified via `docker exec docker-api-1 sh -c 'echo $DATABASE_URL'`
that the running container's actual environment has the value correctly substituted
(`postgresql+asyncpg://testpilot_app:change-me-to-a-random-secret@postgres:5432/testpilot`) —
this is a cosmetic Compose CLI quirk in how it re-evaluates `env_file:`-sourced interpolation
for display purposes, not a functional defect; the real connection worked (readyz confirmed DB
reachability).

## Section 2 — Database migrations

**Method**: Same running stack as Section 1; migrations already applied automatically by the
`api`/`worker` containers' shared entrypoint (`infra/docker/backend-entrypoint.sh`) before
either process starts, per this section's own documented expectation. Manual
`alembic upgrade head` also run directly inside the `api` container to confirm idempotency.

| Check | Result |
|---|---|
| All tables from data-model.md exist | PASS — `\dt` inside `postgres` lists all 24 expected tables (`users`, `organizations`, `memberships`, `subscription_plans`, `projects`, `test_cases`, `test_steps`, `test_runs`, `test_run_cases`, `test_results`, `artifacts`, `ai_analyses`, `issues`, `issue_attachments`, `generation_runs`, `notifications`, `assistant_conversations`, `assistant_messages`, `usage_records`, `audit_log_entries`, `invitations`, `refresh_tokens`, `password_reset_tokens`, `alembic_version`) |
| `subscription_plans` seeded with Free/Starter/Professional/Enterprise | PASS — all four tiers present with correct limits (free: 1 project/50 executions/20 AI ops/1 member; starter: 5/500/200/3; professional: 25/5000/2000/10; enterprise: unlimited/NULL on all four) |
| Manual `alembic upgrade head` is a clean no-op against an already-migrated database | PASS — no output beyond the two `INFO` context lines, confirming idempotency |

## Sections 3-11 — Every MVP user story, end-to-end (T234)

**Method**: The full Playwright E2E suite (`frontend/tests/e2e/*.spec.ts`, 25 tests across 13
files — each explicitly labeled with the quickstart.md section/story it covers) run with
`E2E_BASE_URL=http://localhost:3200` against the same live `docker compose up -d` stack from
Section 1, using `AI_PROVIDER=fake` (per quickstart.md's own Prerequisites: "a local/mock
provider mode is expected to exist for running the suite without a real key"). This is the
mechanized, automated form of manually clicking through Stories 1-9 — every one of these specs
already existed from its own feature phase; nothing new was written to satisfy T234/T239, only
executed together against a real stack for the first time.

| Story | Spec file | Result |
|---|---|---|
| 1 — Sign up and manage an account | `auth.spec.ts` (incl. real Mailhog password-reset flow) | PASS |
| 2 — Create a project | `projects.spec.ts` (3 tests: SSRF rejection, valid creation, archiving) | PASS |
| 3 — Generate AI test cases | `ai-generation.spec.ts` | PASS (after a real bug fix — see below) |
| 4 — Execute a test run | `test-runs.spec.ts`, `test-results.spec.ts` | PASS (after the same fix) |
| 5 — AI failure analysis | `ai-analysis.spec.ts` | PASS (after the same fix) |
| 6 — Test case library management | `test-cases-library.spec.ts` | PASS |
| 7 — Bug/issue tracking | `issues.spec.ts` (2 tests) | PASS |
| 8 — Reports | `reports.spec.ts` | PASS |
| 9 — Notifications | `notifications.spec.ts` | PASS |
| (dashboard shell, settings/org/billing, landing page — not their own numbered story but exercised by the same run) | `dashboard-shell.spec.ts`, `settings-org-billing.spec.ts` (3 tests), `landing.spec.ts` (4 tests) | PASS |

**Final result: 25/25 passed** (run in three batches of 20+3+2 — see the rate-limit note below
for why; every batch on the same live stack, same session).

### Real bug found and fixed: Playwright browsers installed to the wrong user's cache directory

**Symptom**: every test needing real browser automation (AI generation's site-analysis crawl,
test execution, AI analysis, which all go through `execution.playwright_engine.PlaywrightEngine`)
failed or hung — surfacing initially as confusing, inconsistent E2E failures (a `generation_run`
reaching `status=failed` with `failure_reason="No testable public content was found at
https://example.com"`; a test run never reaching a `Completed` state; a result missing its
expected screenshot) with **no exception ever visible in the worker's own logs**, because
NFR-007's own fault-isolation design (a test case's engine-level exception is caught and
recorded as that case's `error` result, not surfaced as a job failure) silently absorbed it.

**Root cause**: `infra/docker/backend.Dockerfile` runs `playwright install --with-deps chromium`
as `root` (required for the `apt`-based OS dependency install), *before* the `testpilot` non-root
user is created and switched to. Playwright's browser cache is per-user
(`~/.cache/ms-playwright`) with no explicit `PLAYWRIGHT_BROWSERS_PATH` set — so the browsers were
installed into `/root/.cache/ms-playwright`, invisible to the actual runtime process running as
`testpilot`. Confirmed directly: `docker exec docker-worker-1 python -c "...PlaywrightEngine...
load_page(...)"` raised `playwright._impl._errors.Error: BrowserType.launch: Executable doesn't
exist at /home/testpilot/.cache/ms-playwright/...`, while the same browsers were present and
intact under `/root/.cache/ms-playwright/`.

**Fix**: set `ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright` (a location outside any per-user home
directory) before the install step, and `chmod -R a+rX /ms-playwright` after, so both the
root-run install step and the testpilot-run application process agree on one shared, readable
location.

**Verification**: rebuilt the image (`docker compose up -d --build`), reran the same direct
`PlaywrightEngine.load_page()` check (succeeded), then reran the full E2E suite — all
previously-failing generation/execution/analysis specs passed.

### Environmental note: signup's rate limit and full-suite pacing

`POST /auth/signup` is rate-limited to 5/minute per IP (SEC-009, `@limiter.limit("5/minute")` in
`api/v1/auth.py`) — a deliberate, correct security control, unrelated to and not weakened by this
finding. Running the *entire* 25-test suite in one `npx playwright test` invocation — even fully
serial (`--workers=1`) — accumulates more than 5 signups within the rate limiter's 1-minute
window purely from the suite's own total real-world runtime (~2.5 minutes for ~30+ cumulative
signups across all specs), since every test signs up its own fresh account for isolation. This
produced spurious `expect(page).toHaveURL(/\/overview$/)` failures (landed back on `/signup`,
the 429 response) unrelated to any of the features under test. Splitting the run into smaller
batches (each comfortably under 5 signups/minute) reproduces a clean, complete pass — this is a
property of automated-test pacing against a rate-limited real backend, not a defect in the
rate limiter or the suite. CI's own `backend-tests` job is unaffected: it runs with
`ENVIRONMENT=test`, where `api/deps.py`'s limiter is deliberately disabled.

## Section 12 — Tenant isolation validation (T235)

**Method**: Real HTTP requests (`curl`) against the live stack — two freshly signed-up accounts
(Tenant A, Tenant B), Tenant A creates a project, an approved test case, a test run, and an
issue; Tenant B (a different Organization) then requests each of Tenant A's resources by ID.

| Resource | Result |
|---|---|
| `GET /projects/{tenant_a_project_id}` as Tenant B | PASS — `404 not_found`, never `403` |
| `GET /projects/{id}/test-runs/{tenant_a_run_id}` as Tenant B | PASS — `404 not_found` |
| `GET /projects/{id}/issues/{tenant_a_issue_id}` as Tenant B | PASS — `404 not_found` |

Matches FR-136/SEC-011 exactly as quickstart.md specifies — indistinguishable from a nonexistent
ID in every case.

## Section 13 — Plan-limit validation (T236)

**Method**: `testpilot-cli billing set-plan <org_id> free --max-projects=1` (the CLI entrypoint
built this same phase — T238, see below) run against the live stack's own Postgres/Redis
(`localhost:5435`/`localhost:6381`, the docker-compose stack's published ports), then a second
`POST /projects` attempted via the live API.

| Check | Result |
|---|---|
| First project (within limit) | PASS — `201`, `status=active` |
| `testpilot-cli billing set-plan` sets the limit | PASS — `{"max_projects": 1, ...}` confirmed via `--json` output |
| Second project (over limit) | PASS — `402`, `{"error":{"code":"plan_limit_exceeded","message":"Organization has reached its projects limit","details":{"limit":"projects","used":1,"max":1}}}` |
| Second project not actually created | PASS — `GET /projects` still lists exactly the one project afterward |

## Section 14 — Accessibility/responsive spot-check (T237)

**Method**: A one-time Playwright script (not committed — quickstart.md Section 14 is a
validation exercise, not a request for a new permanent E2E spec) against the live stack.

| Check | Result |
|---|---|
| Keyboard-only signup (Tab between fields, Enter to submit, no `.click()`) reaches `/overview` | PASS |
| Visible focus indication on a keyboard-focused field | PASS — confirmed via computed style: `outline: 2px solid` plus a visible indigo box-shadow focus ring |
| Keyboard-only project creation (`/projects/new`, Tab + type + Enter) | PASS — every field reachable and operable, no mouse interaction |
| Mobile viewport (375×667) signup | PASS |
| Mobile viewport: responsive nav (hamburger menu) | PASS — confirmed via accessibility tree: `navigation "Primary"` with `"Open menu"`/`"Close menu"` toggle buttons, full nav list reachable |
| Mobile viewport: test-case library search/filter | PASS — search box visible and usable (confirmed bounding box), typing a query correctly filters results, results render as accessible mobile-friendly cards/buttons (not the desktop table, which is present but CSS-hidden at this width) rather than being unusable |

## Full regression pass (T239)

The 25-test E2E suite run in full for Sections 3-11 above **is** the "re-run every phase's E2E
suite together" regression pass tasks.md's own T239 asks for — run against the one live stack,
same session, immediately after the Playwright-browser-path fix, with all 25 tests passing.

## testpilot-cli entrypoint (T238)

**Real bug found and fixed, independent of the above**: `pyproject.toml`'s
`testpilot-cli = "testpilot.cli.main:app"` console-script entry pointed at a module
(`backend/src/testpilot/cli/main.py`) that did not exist — every one of the six per-domain
CLI command groups (`billing`, `projects`, `testcases`, `ai`, `run`, `reports`) was already
built and already tested in its own feature phase, but never assembled into the one
distributable CLI the constitution's CLI Interface principle requires. Running the installed
`testpilot-cli` script raised `ModuleNotFoundError: No module named 'testpilot.cli.main'`.
Fixed by writing `cli/main.py` (final wiring only, `app.add_typer(...)` for each existing
sub-app) — verified both via 7 new unit tests (`tests/unit/cli/test_main_cli.py`) and by
actually running the installed `testpilot-cli --help` / `testpilot-cli billing --help` console
scripts, confirming every subcommand group is reachable, matching quickstart.md Section 13's
own literal invocation shape.

## Known limitation, documented (not a Section 1/2 failure)

`storage/s3.py`'s presigned URLs are generated using the same `endpoint_url` the API/worker
containers use to reach MinIO internally (`http://minio:9000`, the Docker-network service name).
A URL with that host is unreachable from a browser running on the host machine, which cannot
resolve `minio` as a hostname — screenshot/artifact viewing (a later quickstart.md story, not
Section 1 or 2) would be affected by this in the current dockerized setup. No project
requirement (spec.md, plan.md, research.md, contracts/) currently defines a distinct "public"
storage endpoint setting to resolve this, so it is out of this phase's scope to invent one;
flagged here for visibility rather than silently left undiscovered.

## CI/CD pipeline validation, post-Phase 26

Phase 24 built `.github/workflows/ci.yml`, and its own checkpoint report validated the workflow
file (actionlint, local reproduction of each job's commands) — but the workflow had never
actually **executed** as a real GitHub Actions run until this pass, which is what surfaced the
four issues below. None of these are quickstart.md-numbered sections; recorded here because they
were found and fixed through the same "run it for real, don't just inspect the file" discipline
as the rest of this document, on the pushed repository
(`github.com/muhammadArsalaanAkbar/testpilot-ai-platform`).

### Real bug found and fixed: CI had never run at all (`main`/`master` branch mismatch)

**Symptom**: A CI status badge added to `README.md` rendered "no status"/404 rather than
pass/fail.

**Root cause**: `ci.yml`'s trigger was `on: push: branches: [main]`, but the repository's actual
(and only) branch is `master` — every push since the initial commit silently failed to match,
so the workflow had zero runs in its history. Confirmed via the GitHub Actions API
(`/actions/workflows`, `/actions/runs`): only GitHub's own automatic Dependabot dependency-graph
job had ever run.

**Fix**: `branches: [main]` → `branches: [master]`, plus the 3 `github.ref ==
'refs/heads/main'` conditionals (GHCR login, both `docker/build-push-action` `push:` gates).

**Verification**: pushed the fix; the workflow registered in `/actions/workflows` for the first
time and a real run started immediately.

### Real bug found and fixed: `pip-audit` false failure (auditing our own unpublished package)

**Symptom**: `backend-dependency-audit` failed on the workflow's first-ever run:
`pip_audit._cli: testpilot: Dependency not found on PyPI and could not be audited`.

**Root cause**: the job's `uv export --format requirements.txt --extra dev --no-hashes` step
included the local, unpublished `testpilot` package itself (via its `-e .` entry) in the
exported requirements file — `pip-audit` then tried to look `testpilot` up on PyPI as if it were
a real third-party dependency and failed. Not a real vulnerability.

**Fix**: added `--no-emit-project` to the `uv export` command, excluding the local package from
the audit input.

**Verification**: reproduced locally first (`uv run pip-audit --strict -r
requirements-audit.txt` failed identically without the flag, passed with `No known
vulnerabilities found` after), then confirmed green on the real CI run for the fix commit.

### Real bug found and fixed: 9 npm high/critical/moderate vulnerabilities (`next`, `vitest`)

**Symptom**: `frontend-dependency-audit` (`npm audit --audit-level=high`) failed once CI could
finally run it: 9 vulnerabilities (3 moderate, 5 high, 1 critical).

**Root cause**: `next@15.5.22` bundled a vulnerable `postcss` (8.4.31) and `sharp` (<0.35.0), and
no patched stable 15.x release exists (only unreleased 15.6 canaries) — the fix requires 16.x.
Separately, `vitest@2.1.9` itself carried a **critical** CVE (GHSA-5xrq-8626-4rwp: arbitrary file
read/execute via its UI server), fixed in >=3.2.6, dragging in the same-tree `esbuild`/`vite`/
`vite-node`/`@vitest/mocker` moderate findings.

**Fix**: `next` 15.0.3 → 16.3.0 (`react`/`react-dom` stayed at 18.3.1 — Next 16 still accepts
React 18 as a peer, so no forced React major bump; `eslint-config-next` stayed at 15.x too, since
it has no hard peer on `next`'s own version and bumping it would have forced an unrelated ESLint
9 migration). `vitest` 2.1.9 → 3.2.7, which also resolved `vite` to 7.3.6 and `esbuild` to
0.28.2. `nanoid` resolved to 3.3.18 within `postcss`'s existing `^3.3.16` range via `npm update`.

**Verification**: `npm audit --audit-level=high` → `found 0 vulnerabilities`. Full regression
before committing: frontend unit tests (30/30), `tsc --noEmit`, `eslint`, `next build`
(Turbopack), and the full 25-test Playwright E2E suite — all against a live
Postgres+Redis+MinIO+Mailhog stack with a real API/worker (required fixing this session's own
local verification setup along the way: RQ's default fork-based `Worker` doesn't run on Windows,
`os.fork` doesn't exist there, so verification used `SimpleWorker` instead — a
verification-environment-only detail, not a production concern since workers always run in Linux
containers). Backend regression (unrelated files, run as a release-process check): ruff, mypy,
`alembic check`, and pytest (372/373 — the one failure reproduced as a pre-existing load-related
flake, passing cleanly in isolation, unrelated to this change).

### Real bug found and fixed: `backend-tests` had never actually passed in CI (missing MinIO)

**Symptom**: `backend-tests` failed on the first real CI run, and again on a targeted
`rerun-failed-jobs` re-run (ruling out a flake before investigating further) — 5 failures, all
`botocore.exceptions.NoCredentialsError` or a missing-attachment assertion.

**Root cause**: `backend-tests` provisions only `postgres`/`redis` GitHub Actions service
containers — no MinIO, since (per the job's own existing comment) `minio/minio`'s default image
entrypoint doesn't start the server and GitHub's native `services:` block has no way to override
a container's command. Two whole files were already excluded from the test run for this exact
reason (`test_artifact_storage.py`, `test_artifact_retention.py`), but 5 *individual* tests in
otherwise storage-independent files — `test_issues.py` (3), `test_test_results.py` (1),
`test_issues_from_result.py` (1) — also create a failed result, which captures a real screenshot
through the storage adapter, and were never added to the exclusion. This is why it was never
caught before: the branch-mismatch bug above meant this job had never executed in GitHub Actions
at all until now.

**Fix**: added `--deselect` for the exact 5 test IDs (not `--ignore` for their whole files) — the
other 22 tests across those 3 files don't touch storage and still run in CI.

**Verification**: `pytest --collect-only` confirmed exactly 5 deselected (358/363 collected); a
full local run with the identical CI flags passed 358/358. Pushed and confirmed via the GitHub
Actions API: 9/9 jobs green, including `docker-images` (previously blocked by `backend-tests`
never passing) successfully building and pushing all three images to GHCR for the first time.

## Validation environment notes

This machine already runs long-lived, manually-started containers (`testpilot-postgres`,
`testpilot-redis`, `testpilot-minio`, `testpilot-mailhog`) on the same host ports this
docker-compose stack uses, predating this phase's work and relied on by the rest of this
project's test suite (`backend/.env`, `backend/.env.test`). They were stopped (not removed —
fully reversible, no data loss) immediately before this validation and restarted immediately
after, so this validation's `docker compose` stack and its own named volumes
(`docker_postgres_data`, `docker_minio_data`) are a separate, independent environment from the
one the rest of this session's backend tests run against.
