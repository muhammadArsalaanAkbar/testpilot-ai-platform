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
  names (`testpilot-api:latest`, etc.) rather than `ghcr.io/<owner>/<repo>-api:sha-...`/a real
  digest. `overlays/production/` (see below) is where Kustomize's `images:` transformer remaps
  these to a real registry/digest without editing this base.
- **A real Ingress host/TLS.** `testpilot.example.com` is a placeholder, as is the
  `ingressClassName: nginx` (swap for whatever ingress controller the target cluster runs). No
  cert-manager/TLS config is included in `base/` — `overlays/production/` adds a TLS-ready patch
  (see below), still with a placeholder host/issuer name of its own.
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

## The production overlay (`overlays/production/`)

Everything above (`base/`) is still the unmodified, cluster-agnostic shape. `overlays/production/`
is a real Kustomize overlay on top of it — it does not edit any file under `base/`; every
difference below is a patch, generator, or transformer applied at render time.

| File | What it does |
|---|---|
| `overlays/production/kustomization.yaml` | Ties everything below together: `resources: [../../base, namespace.yaml]`, `namespace: testpilot-production`, the `images:` digest-pin transformer, the two `patches:`, and the `secretGenerator`. |
| `overlays/production/namespace.yaml` | A `Namespace` resource (`base/` deliberately declares none — see above); `namespace:` in the kustomization stamps it onto every `base/` resource too. |
| `overlays/production/config-patch.yaml` | Strategic-merge patch overriding only `testpilot-config`'s `CORS_ALLOWED_ORIGINS` key — everything else in the ConfigMap still comes from `base/config.yaml` untouched. |
| `overlays/production/ingress-patch.yaml` | JSON6902 patch: sets the real host, `ingressClassName`, adds a `tls:` block and a `cert-manager.io/cluster-issuer` annotation to `base/service-ingress.yaml`'s `Ingress` — without touching its existing annotation or path rules. |
| `overlays/production/secrets.env.example` | Committed **template** (all `REPLACE_ME_*`/documented placeholders) for the real secret values — see "Configuring the production overlay" below. |

**What's still a placeholder, by design** — matching `base/`'s own "not a real X" list above, this
overlay does not invent real values for any of these either:

- `testpilot.example.com` (both `ingress-patch.yaml`'s host and `config-patch.yaml`'s CORS value)
- `REPLACE_ME_CLUSTER_ISSUER_NAME` (`ingress-patch.yaml`'s cert-manager annotation)
- Every key in `secrets.env.example` (real credentials, `DATABASE_URL`, `REDIS_URL`, and —
  important, see below — `OBJECT_STORAGE_ENDPOINT_URL`)
- `ingressClassName: nginx` (same placeholder as `base/`, just now overlay-owned so a real
  deployment edits `ingress-patch.yaml` instead of `base/service-ingress.yaml`)

**What is real** — the three image references pinned in `kustomization.yaml`'s `images:` block
are genuine GHCR digests, not placeholders: the last commit whose `docker-images` CI job was
independently re-verified (`docker pull` + a real `PlaywrightEngine.load_page()` call against the
actual pulled image — see `docs/RELEASE.md`'s Verification record), not merely "CI reported
success."

### Configuring the production overlay

1. **Domain**: replace `testpilot.example.com` in **both** `ingress-patch.yaml`'s
   `/spec/rules/0/host` and `/spec/tls/0/hosts/0`, **and** `config-patch.yaml`'s
   `CORS_ALLOWED_ORIGINS` — these two files must stay in sync (same convention `base/
   service-ingress.yaml`'s own comment already documents for this exact value; nothing in
   Kustomize enforces this automatically, since these are two independent patches).

2. **Ingress controller**: replace `ingress-patch.yaml`'s `ingressClassName: nginx` with whatever
   the target cluster actually runs (`traefik`, `alb`, `gce`, etc.). If it isn't nginx, the
   `nginx.ingress.kubernetes.io/use-regex` annotation inherited from `base/service-ingress.yaml`
   is also meaningless for that controller — remove it via an additional patch op if so.

3. **TLS**: two supported shapes, pick one:
   - **cert-manager** (if already installed in the target cluster with a `ClusterIssuer`
     configured): replace `ingress-patch.yaml`'s `REPLACE_ME_CLUSTER_ISSUER_NAME` with that
     issuer's real name. cert-manager will then watch the Ingress and create/renew a certificate
     into the `testpilot-tls` Secret automatically — no certificate is ever committed here.
   - **A pre-existing Kubernetes TLS Secret**: delete the `cert-manager.io/cluster-issuer`
     annotation `op` from `ingress-patch.yaml`, and create the `testpilot-tls` Secret yourself
     before applying — `kubectl create secret tls testpilot-tls --cert=fullchain.pem
     --key=privkey.pem -n testpilot-production`. `ingress-patch.yaml`'s `tls:` block already
     points at that Secret name either way.

4. **Public object storage endpoint** (`OBJECT_STORAGE_ENDPOINT_URL` in `secrets.env`) — the
   presigned-URL problem `docs/RELEASE.md` and `quickstart-results.md` already document: this
   value is used both by the API/worker to reach storage internally **and** to sign URLs handed
   directly to a user's browser. A cluster-internal hostname here (e.g. a Kubernetes-Service-only
   MinIO) means every real user's browser fails to load screenshots/artifacts, since it cannot
   resolve that hostname. This overlay does **not** invent a value — you must supply a genuinely
   publicly-reachable S3-compatible endpoint (a real AWS S3 bucket's regional endpoint, or a
   self-hosted MinIO/other store sitting behind a public reverse proxy/CDN using the same DNS name
   used for signing).

5. **Secrets**: `cp overlays/production/secrets.env.example overlays/production/secrets.env`, fill
   in every `REPLACE_ME_*` value (`secrets.env` is gitignored — see `.gitignore`'s "Kubernetes
   overlay secrets" section — it is never committed). `kustomization.yaml`'s `secretGenerator`
   (`behavior: replace`) then replaces `base/config.yaml`'s placeholder `testpilot-secrets` Secret
   entirely at render time, with no base file edit and no Deployment `secretRef` name change
   needed. **Prefer not using this file at all** for a real production pipeline — an [External
   Secrets Operator](https://external-secrets.io/) `ExternalSecret`/`SecretStore` pulling from a
   real secrets manager (AWS Secrets Manager, GCP Secret Manager, Vault, etc.) is more
   production-grade; if using that instead, delete the `secretGenerator` block from
   `kustomization.yaml` and let ESO own the `testpilot-secrets` Secret. Either way, something in
   the cluster must produce a Secret named `testpilot-secrets` with `secrets.env.example`'s same
   keys before the Deployments start.

6. **Image tag for a specific release**: the digests pinned in `kustomization.yaml` are frozen to
   one specific, already-verified commit — update them for every new release:

   ```sh
   # Find the digest ci.yml's docker-images job pushed for a given commit:
   docker buildx imagetools inspect ghcr.io/muhammadarsalaanakbar/testpilot-ai-platform-api:sha-<commit-sha>
   # Then edit kustomization.yaml's images: block (or use):
   cd infra/k8s/overlays/production
   kustomize edit set image \
     testpilot-api=ghcr.io/muhammadarsalaanakbar/testpilot-ai-platform-api@sha256:<digest> \
     testpilot-worker=ghcr.io/muhammadarsalaanakbar/testpilot-ai-platform-worker@sha256:<digest> \
     testpilot-frontend=ghcr.io/muhammadarsalaanakbar/testpilot-ai-platform-frontend@sha256:<digest>
   ```

### Deploying

```sh
# Render only (no cluster needed) — sanity-check before applying anything:
kubectl kustomize infra/k8s/overlays/production/

# Apply to a real cluster (requires a working kubeconform context and
# secrets.env / an external-secrets mechanism already set up per step 5 above):
kubectl apply -k infra/k8s/overlays/production/
```

### Verifying the rollout

```sh
kubectl -n testpilot-production get pods -w
kubectl -n testpilot-production rollout status deployment/testpilot-api
kubectl -n testpilot-production rollout status deployment/testpilot-worker
kubectl -n testpilot-production rollout status deployment/testpilot-frontend
kubectl -n testpilot-production get ingress testpilot-ingress
curl https://<your-real-domain>/api/v1/readyz   # {"status":"ok","checks":{"database":"ok","redis":"ok"}}
```

### Validating locally (no cluster required)

```sh
# Render the full overlay
kubectl kustomize infra/k8s/overlays/production/

# kubeconform requires secrets.env to exist (secretGenerator reads it at
# render time) -- copy the example first if you haven't already:
cp infra/k8s/overlays/production/secrets.env.example infra/k8s/overlays/production/secrets.env
kubectl kustomize infra/k8s/overlays/production/ | docker run --rm -i ghcr.io/yannh/kubeconform:latest -summary -strict
rm infra/k8s/overlays/production/secrets.env   # never leave this behind
```

### Known gaps, honestly documented

- **No `securityContext`** on any container (base or overlay) — both images already run as a
  non-root `testpilot` user by their own `Dockerfile`'s `USER` directive (defense already exists
  at the image layer), but there is no Kubernetes-level `runAsNonRoot`/`readOnlyRootFilesystem`/
  capability-drop enforcement backing that up. Deliberately left out of this overlay rather than
  added speculatively: `readOnlyRootFilesystem` in particular would need verifying the worker's
  Playwright/Chromium browser automation still works with no writable root filesystem (temp
  profile directories, downloads) before it could be safely claimed to work — that verification
  was out of this overlay task's scope.
- **HPA/KEDA autoscaling** — still just the documented shape below, not built into this overlay
  either (same "needs real production load data" reasoning as before).
- **`worker`'s liveness probe** — unchanged from `base/`'s own documented gap above (a bare TCP
  check, not a real Redis-reachability check).

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
