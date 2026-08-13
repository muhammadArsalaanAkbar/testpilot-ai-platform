# Release checklist / runbook

**Phase 26 (Final Integration, QA, and Release Preparation), T240.** This is the operational
companion to [`specs/001-testpilot-ai-platform/quickstart.md`](../specs/001-testpilot-ai-platform/quickstart.md)
(validation steps and expected behavior) and
[`specs/001-testpilot-ai-platform/quickstart-results.md`](../specs/001-testpilot-ai-platform/quickstart-results.md)
(the actual, dated results of running them) — read those two first; this file is deploy/rollback
procedure and a release-readiness checklist, not a re-statement of what already works.

## 1. Pre-release checklist

Before cutting a release, confirm every item below — each maps to a real, automated check, not
a manual judgment call:

- [x] `.github/workflows/ci.yml` is green on the release commit: `backend-lint`, `backend-typecheck`,
      `backend-tests`, `backend-dependency-audit`, `frontend-lint`, `frontend-typecheck`,
      `frontend-unit-tests`, `frontend-dependency-audit` all pass (research.md #15's stages 1-2).
- [x] `docker-images` (CI stage 3) built and pushed successfully for the release commit —
      confirms `infra/docker/backend.Dockerfile` and `infra/docker/frontend.Dockerfile` both
      still build cleanly, not just that unit/integration tests pass.
- [x] `cd backend && uv run alembic check` reports no drift between the latest migration and the
      current SQLModel models.
- [x] Real browser automation genuinely works inside the built `api`/`worker` image — CI's own
      test suite mocks/fakes enough of the stack (`AI_PROVIDER=fake`, local fixture URLs) that a
      broken Chromium install inside the image can pass CI while being completely non-functional
      at runtime. Found exactly this once already (Phase 26, T234): browsers installed as `root`
      landed in `/root/.cache/ms-playwright`, invisible to the non-root `testpilot` user the
      container actually runs as — every real browser automation call failed silently, masked by
      NFR-007's own per-step fault isolation (see quickstart-results.md's Sections 3-11 entry for
      the full root cause/fix). Verify directly against the *built image*, not just against
      source: `docker exec <worker-container> python -c "import asyncio; from
      testpilot.execution.playwright_engine import PlaywrightEngine; asyncio.run(PlaywrightEngine().load_page('https://example.com'))"`
      must succeed with no exception.
- [x] `specs/001-testpilot-ai-platform/quickstart-results.md` has a dated entry for every
      section (1-14) with no unresolved FAIL rows — re-run `quickstart.md` end-to-end against a
      fresh `docker compose up` if the last recorded run predates the release commit by more
      than a trivial change.
- [x] No `TODO`/`FIXME` markers were introduced against a Security Requirement (SEC-001–SEC-013)
      or Data Requirement (DATA-001–DATA-007) — those are MVP-required per spec.md's MVP Scope,
      not deferrable polish.
- [x] `infra/k8s/base/config.yaml`'s `Secret` still contains only `REPLACE_ME_*` placeholders —
      if a real credential was ever pasted in during local testing, confirm it was never
      committed (SEC-004).

### Verification record (release commit `ae9bfaf`, `master`, 2026-08-14)

Each item above was independently re-verified against this exact commit before checking it off —
not carried over from an earlier commit's result:

1. **CI green**: GitHub Actions run
   [31735629246](https://github.com/muhammadArsalaanAkbar/testpilot-ai-platform/actions/runs/31735629246)
   for commit `ae9bfafe9edf4046ff5621b19dd6a5380b5d60b4` — 9/9 jobs `success` (the 9th,
   `docker-images`, is stage 3, covered by the next item).
2. **`docker-images`**: same run, job `success` — pushed
   `ghcr.io/muhammadarsalaanakbar/testpilot-ai-platform-{api,worker}:sha-ae9bfafe9…` and
   `...-frontend:sha-ae9bfafe9…` (digest `sha256:70aa966f…` for api/worker). Confirmed by pulling
   the worker image back down directly from GHCR (not trusting the CI log alone) —
   `docker pull` succeeded, image present locally at 2.04GB.
3. **`alembic check`**: run locally against the reused Postgres container —
   `No new upgrade operations detected.` (exit 0).
4. **Real browser automation in the built image**: ran the checklist's own command against the
   *actual pulled* `sha-ae9bfafe9…` worker image (with `--entrypoint python` to bypass the
   image's migration-on-start entrypoint, and placeholder DB/Redis/JWT env vars — this check
   never touches the database, only Playwright/Chromium) —
   `PlaywrightEngine().load_page("https://example.com")` completed and printed a success marker,
   exit code 0. (A benign `RuntimeError: Event loop is closed` appears on stderr after that
   success marker — a known asyncio/subprocess finalizer warning during Python interpreter
   shutdown on Linux, not an exception from `load_page()` itself.)
5. **`quickstart-results.md`**: sections 1–14 all present, zero `FAIL` occurrences in the file.
   The underlying app code has not changed since the 2026-08-13 E2E run recorded there — only
   `ci.yml` and documentation changed afterward — so that run still reflects the release commit's
   actual behavior; no re-run was needed.
6. **No `TODO`/`FIXME`**: `grep -rn "TODO\|FIXME" backend/src/ frontend/src/` — zero matches
   anywhere in application source, not just near security/data requirements.
7. **k8s `Secret` placeholders**: current `infra/k8s/base/config.yaml` contains only
   `REPLACE_ME_*` values (`SENTRY_DSN` is deliberately empty, matching `.env.example`'s own
   "optional locally" pattern — not a placeholder standing in for a real value). Checked the
   file's entire git history (`git log --all -p`) — only one commit has ever touched it, and no
   non-placeholder credential value was ever committed.

## 2. Deploy steps

### 2a. Local / single-host (docker-compose) — what quickstart.md Section 1 already validates

```sh
cp infra/docker/.env.example infra/docker/.env   # fill in real values — every REPLACE_ME_*
docker compose -f infra/docker/docker-compose.yml up -d --build
```

Migrations apply automatically (`infra/docker/backend-entrypoint.sh`, run by both `api` and
`worker` at container start — idempotent, safe for both to run). Verify:

```sh
curl http://localhost:8000/api/v1/healthz   # {"status":"ok"}
curl http://localhost:8000/api/v1/readyz    # {"status":"ok","checks":{"database":"ok","redis":"ok"}}
```

### 2b. Kubernetes (base manifests only — `infra/k8s/`, Phase 25)

`infra/k8s/base/` is **not** a ready-to-apply production deployment — it is the documented
manifest *shape* (plan.md's Kubernetes-Readiness section), validated structurally (see
`infra/k8s/README.md` for exactly how) but never applied against a real cluster with real
values. Before applying anywhere real:

1. Build/push real images (CI stage 3 already does this on merge to `main` —
   `ghcr.io/<owner>/<repo>-{api,worker,frontend}:sha-<commit>`).
2. Create an environment-specific overlay under `infra/k8s/overlays/<env>/` (not built yet —
   Future) that:
   - Uses Kustomize's `images:` transformer to remap `deployments.yaml`'s placeholder image
     names (`testpilot-api:latest` etc.) to the real pushed tags.
   - Replaces `config.yaml`'s `Secret` with a real secrets-management mechanism (External
     Secrets Operator, Sealed Secrets, or a CI/CD-injected `kubectl create secret` — never a
     committed value, per SEC-004).
   - Sets `service-ingress.yaml`'s `testpilot.example.com` placeholder host and a real
     `ingressClassName` matching the target cluster's ingress controller.
3. `kubectl apply -k infra/k8s/overlays/<env>/`
4. Point `frontend.Dockerfile`'s `NEXT_PUBLIC_API_BASE_URL` build ARG at the real API's public
   URL when building the frontend image for this environment (it is baked in at image-build
   time, not read at container-start time — see the Dockerfile's own comment).

**Known gap, honestly documented, not silently glossed over**: `storage/s3.py`'s presigned URLs
are generated using the same internal `endpoint_url` the API/worker use to reach the object
store — if that's a cluster-internal hostname, a browser on the public internet cannot resolve
it. No project requirement currently defines a distinct "public" storage endpoint setting to
solve this (see `quickstart-results.md`'s Section 1/2 notes, where this was first found against
docker-compose) — a real deployment needs a publicly-reachable S3/MinIO endpoint (or a
CloudFront/reverse-proxy fronting it) before screenshot/artifact viewing works outside the
cluster's own network.

## 3. Rollback

- **docker-compose**: `docker compose -f infra/docker/docker-compose.yml down`, then
  `docker compose up -d` against the previous release's checked-out commit (images rebuild from
  that commit's Dockerfiles) or the previous `:sha-<commit>` tag if pulling pre-built images.
  `postgres_data`/`minio_data` are named volumes, not removed by `down` alone — a schema
  rollback additionally requires `alembic downgrade <previous-revision>` run manually (no
  automatic down-migration step exists in the entrypoint, by design — forward-only migrations
  are the default assumption; only run `downgrade` if the new release's migration is confirmed
  safe to reverse).
- **Kubernetes**: `kubectl rollout undo deployment/testpilot-api -n <namespace>` (and
  `testpilot-worker`, `testpilot-frontend` — each Deployment rolls back independently, matching
  their independent replica-count/scaling design). Database migrations are **not** rolled back
  automatically by this — same manual `alembic downgrade` caveat as above applies.
- **Emergency stop**: scale `worker` to 0 replicas first if a bad release is actively producing
  incorrect test-execution results — this stops new job processing immediately without needing
  a full rollback, buying time to investigate (`kubectl scale deployment/testpilot-worker
  --replicas=0` or `docker compose stop worker`).

## 4. Known Future-scope gaps (spec.md's own MVP Scope § Future Scope — not release blockers)

Every item below is an explicit, spec-documented deferral, not an oversight:

1. Authenticated-flow testing / site-under-test credential storage (FR-048; SEC-005's
   absence-of-capability is intentional at MVP).
2. Full multi-member Organizations — invitations, roles beyond a single Owner, member removal
   (FR-016–FR-019, FR-094). The invitations API/table exist (schema-ready) but the actual
   invite-accept flow is a `501 Not Implemented` stub.
3. AI QA Assistant conversational interface (FR-097–FR-103, FR-023) — `POST /assistant/chat`
   is a `501` stub; the schema (`assistant_conversations`/`assistant_messages`) exists.
4. Trend reporting, Organization-level rollup reports, report export (FR-108–FR-109, FR-111).
5. Additional notification channels (email/webhook) and per-user notification preferences
   (FR-117–FR-118) — in-app notifications only at MVP.
6. Plan upgrades/downgrades and live payment provider integration (FR-126–FR-127, INT-005) —
   `testpilot-cli billing set-plan` is an admin/test-only override, not a real billing flow.
7. Parallel test execution within/across runs, and run cancellation (FR-077–FR-078).
8. Bulk test case operations (FR-058).
9. Project tagging/grouping for agency-style multi-client management (FR-034).
10. External CI/CD webhook triggers and chat-platform notification integrations
    (INT-006–INT-007).

Additionally, deferred at the infrastructure layer (Phase 24/25, not spec-level Future Scope but
still real, documented gaps):

- **Worker HPA/KEDA autoscaling** — documented shape only in `infra/k8s/README.md`; needs real
  production load data to tune thresholds meaningfully.
- **`infra/k8s/overlays/`** — no environment-specific overlay exists yet (see §2b above).
- **Worker's own liveness probe** is a bare TCP check against its metrics port, not a genuine
  Redis-reachability check (no dedicated worker health-check command exists — see
  `infra/k8s/README.md`'s own probe documentation for the honest limitation).
- **Deployment/staging/production promotion pipeline** — plan.md's CI/CD section explicitly
  scopes CI to build-and-push only; promotion itself was never in scope for this plan.
