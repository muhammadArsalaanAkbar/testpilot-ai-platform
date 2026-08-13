# Kubernetes manifests

Phase 25 (Kubernetes Readiness) scope, per `specs/001-testpilot-ai-platform/plan.md`'s
Kubernetes-Readiness section and `tasks.md`'s T229–T233: the documented manifest *shape* made
concrete, still not deployed anywhere as part of the task list that produced it. `infra/k8s/base/`
is a plain [Kustomize](https://kustomize.io/) base — no cluster-specific values, no live
deployment target.

## What's here

| File | Contents |
|---|---|
| `base/deployments.yaml` | One `Deployment` each for `api`, `worker`, `frontend` — independent replica counts (NFR-005/NFR-006: worker scales for test-execution throughput independent of the API layer), resource requests/limits, liveness/readiness probes (see below) |
| `base/service-ingress.yaml` | `ClusterIP` Services for `api` and `frontend`, one `Ingress` routing `/api` and `/` to them. `worker` has no inbound HTTP traffic to route, so it gets neither. |
| `base/config.yaml` | A `ConfigMap` for non-secret `Settings` fields and a `Secret` **template** (every value a `REPLACE_ME_...` placeholder) for credential-bearing ones |
| `base/kustomization.yaml` | Ties the three files above into one applyable unit |

## What's deliberately NOT here

- **postgres/redis/minio manifests.** plan.md's own shape scopes Kubernetes-readiness to the
  three images this project builds (`api`/`worker`/`frontend` — Research #16); a real cluster is
  expected to consume Postgres/Redis/S3 as externally managed services (e.g. a managed RDS/
  ElastiCache/S3), not as Deployments this repo runs.
- **Real secret values.** `base/config.yaml`'s `Secret` is a template — SEC-004 requires secrets
  be injected via a real secrets-management mechanism at deploy time (External Secrets Operator,
  Sealed Secrets, or a CI/CD-injected `kubectl create secret`), never committed to source
  control. Applying this base as-is to a real cluster will start containers that fail to connect
  to anything, by design — that failure is the intended signal that the placeholders were never
  replaced.
- **A real image registry/tag.** `deployments.yaml`'s `image:` fields use plain, unqualified
  names (`testpilot-api:latest`, etc.) rather than `ghcr.io/<owner>/<repo>-api:sha-...` (the
  format Phase 24's `.github/workflows/ci.yml` `docker-images` job actually pushes). An
  environment-specific overlay under `infra/k8s/overlays/` (Future — not built in this phase) is
  where Kustomize's `images:` transformer would remap these to a real registry/tag without
  editing this base.
- **A real Ingress host/TLS.** `testpilot.example.com` is a placeholder, as is the
  `ingressClassName: nginx` (swap for whatever ingress controller the target cluster runs). No
  cert-manager/TLS config is included — a Future overlay concern.
- **Helm.** Nothing in this project's plan/tasks calls for a Helm chart; the pre-scaffolded
  `base/` + `overlays/` directory shape is Kustomize's own convention, so that's what this phase
  used.

## Liveness/readiness probes (T232, NFR-010)

- **`api`**: `livenessProbe` → `GET /api/v1/healthz` (liveness only, no dependency checks —
  restarts the process only if it's itself wedged). `readinessProbe` → `GET /api/v1/readyz`
  (checks Postgres + Redis reachability — see `backend/src/testpilot/api/v1/health.py`).
- **`frontend`**: both probes → `GET /` (the Next.js standalone server's own root route).
- **`worker`**: a bare `tcpSocket` connect to its Prometheus metrics port (9200, from Phase 22's
  `worker/main.py`). This is a **known, documented gap**, not a false claim of completeness: the
  worker process has no HTTP server of its own to answer a real `/healthz`-equivalent the way
  `api` does, so a TCP-connect-to-metrics-port check only confirms the process is alive and that
  one port is bound — it does **not** verify Redis reachability, unlike plan.md's aspirational
  "an equivalent liveness check on the worker process (can it reach Redis)" language. Building a
  dedicated worker health-check command is application code, out of this DevOps-only phase's
  scope.

## Validating locally (no cluster required)

```sh
# Render the full manifest set
kubectl kustomize infra/k8s/base/

# Validate every rendered resource against the real Kubernetes OpenAPI
# schema, offline (no live cluster needed)
kubectl kustomize infra/k8s/base/ | docker run --rm -i ghcr.io/yannh/kubeconform:latest -summary -strict
```

## Future: HPA/KEDA queue-depth autoscaling (T233 — not implemented this phase)

plan.md's Kubernetes-Readiness section documents, but explicitly defers, a horizontal pod
autoscaling hook for `worker`:

> a documented future HPA hook on worker queue depth (e.g., via KEDA scaling on Redis queue
> length) once real production load data exists to tune it

**Why not now**: HPA/KEDA scaling thresholds (target queue depth per replica, scale-up/down
cooldowns, min/max replica bounds) need real production load data to tune meaningfully — picking
numbers with no data behind them would be guessing, not a documented decision, and risks either
under-provisioning during real load spikes or thrashing replicas on noise. This matches the
constitution's Simplicity principle: this is deliberately-deferred complexity tied to a specific
future need (real load data), not spec/plan/tasks.md scope this phase should invent numbers for.

**What the hook would look like, when that data exists** (documented shape, not implemented):

- [KEDA](https://keda.sh/)'s `ScaledObject` CRD, targeting the `testpilot-worker` Deployment
  above, with a `redis` scaler (KEDA ships one) pointed at the three queue keys
  `worker/queues.py` already defines (`ai-generation`, `test-execution`, `ai-analysis` — RQ's own
  Redis list-length per queue is exactly what the scaler would read, the same value
  `core/metrics.py`'s `queue_depth_collector` already exposes via Prometheus for observability).
- A `minReplicaCount`/`maxReplicaCount` bound and a target queue length per replica, both tuned
  from real throughput numbers (jobs/sec a single worker replica sustains, acceptable queue-wait
  latency) — neither of which exists yet pre-launch.
- Applied as an environment-specific overlay addition (`infra/k8s/overlays/`), not a change to
  this base — the base's `testpilot-worker` Deployment's `replicas: 2` stays the manually-set
  floor a `ScaledObject` would scale from.
