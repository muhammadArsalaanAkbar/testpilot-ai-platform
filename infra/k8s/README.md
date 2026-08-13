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

### External Secrets Operator (alternative)

Step 5 above ("Secrets") describes **Option A**: Kustomize's own `secretGenerator`, reading a
gitignored `secrets.env` file. `overlays/production/external-secret.yaml.example` is **Option
B**: an [External Secrets Operator](https://external-secrets.io/) (ESO) `ExternalSecret` example
that produces the exact same `testpilot-secrets` Secret a different way — by pulling values from
a real external secrets manager into the cluster, rather than from a local file at render time.

**What it's doing**: ESO runs a controller in the cluster that watches `ExternalSecret` resources,
fetches the values each one's `data[].remoteRef` points to from whatever `SecretStore`/
`ClusterSecretStore` it references, and writes them into a real Kubernetes `Secret` (here, still
named `testpilot-secrets` — `base/deployments.yaml`'s `secretRef: name: testpilot-secrets` needs
no change no matter which option produces it). `refreshInterval: 1h` means ESO re-fetches and
updates the Secret periodically, so rotating a credential in the external manager propagates to
the cluster without a redeploy — something Option A's one-shot `secretGenerator` render cannot do.

**Prerequisites this repo does not provide** (deliberately — see the "Do NOT install or configure
a real external secret provider" scope note this file's own header inherits from `base/`'s "not
here" list):

1. **ESO itself must already be installed** in the target cluster (its own Helm chart/manifests —
   not something `infra/k8s/` includes, since it's cluster-wide infrastructure, not
   application-specific).
2. **A real `SecretStore` or `ClusterSecretStore` must already exist**, configured for whichever
   secrets manager you actually use (AWS Secrets Manager, GCP Secret Manager, Azure Key Vault,
   HashiCorp Vault, etc. — ESO supports all of these and more via provider-specific `SecretStore`
   config). `external-secret.yaml.example`'s `secretStoreRef.name: replace-me-secret-store-name`
   is a syntactically valid but entirely fake placeholder (it must pass Kubernetes' own resource-name
   validation, hence lowercase-hyphenated rather than `REPLACE_ME_...` like this repo's other
   placeholders) — not a `SecretStore` this repo creates or assumes exists.
3. **The real secret values must already live in that external secrets manager**, at whatever
   paths/keys you choose — `external-secret.yaml.example`'s `remoteRef.key` values
   (`testpilot/production/database-url` etc.) are illustrative path shapes, not real locations.

**How the mapping works**: each `data[]` entry's `secretKey` (left side) is the key that appears
in the resulting Kubernetes `Secret` — these are not illustrative, they match
`secrets.env.example`/`base/config.yaml`'s Secret keys exactly (`DATABASE_URL`,
`MIGRATIONS_DATABASE_URL`, `REDIS_URL`, `JWT_SIGNING_KEY`, `AI_PROVIDER_API_KEY`,
`OBJECT_STORAGE_ENDPOINT_URL`, `OBJECT_STORAGE_ACCESS_KEY`, `OBJECT_STORAGE_SECRET_KEY`,
`SENTRY_DSN`, `SMTP_HOST` — the same ten keys `testpilot.core.config.Settings` reads via
`envFrom: secretRef:`). Each entry's `remoteRef` (right side) is where ESO fetches that one
value from in your real secrets manager — this part genuinely is provider-specific and this repo
cannot pre-fill it. A provider-neutral illustrative `SecretStore` shape (not committed as an
applyable resource anywhere in this repo, since it would either be misleadingly fake or require
picking one specific provider this repo doesn't commit to):

```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: replace-me-secret-store-name
spec:
  provider:
    # One of ESO's supported provider blocks goes here instead --
    # awsSecretsManager, gcpSecretManager, azurekv, vault, etc. Each has
    # its own auth/config shape; see https://external-secrets.io/latest/provider/
    REPLACE_ME_PROVIDER_BLOCK: {}
```

**Only one option may be active at a time** (requirement: never two competing Secret resources).
To switch from Option A to Option B:

1. `mv overlays/production/external-secret.yaml.example overlays/production/external-secret.yaml`
2. Add `- external-secret.yaml` to `kustomization.yaml`'s `resources:` list.
3. **Delete** the `secretGenerator:` block from `kustomization.yaml` entirely — leaving both
   active means Kustomize's generator and ESO's controller would both try to own
   `testpilot-secrets`, and whichever applies/reconciles last wins non-deterministically.
4. Fill in `external-secret.yaml`'s real `secretStoreRef.name` and every `remoteRef.key`.
5. Confirm ESO and a real `SecretStore`/`ClusterSecretStore` already exist in the target cluster
   (steps 1-2 above) — `kubectl apply -k` will fail at the `ExternalSecret` resource, clearly, if
   the CRD isn't installed; it will not silently do nothing.

**Example deployment flow with Option B enabled**:

```sh
# 1. (Cluster operator, once, outside this repo): install ESO, create a
#    SecretStore/ClusterSecretStore, populate the real secrets manager.
# 2. Render/validate (does NOT require ESO installed locally -- this is
#    just YAML rendering, no live cluster call):
kubectl kustomize infra/k8s/overlays/production/
# 3. Apply -- ESO's controller (already running in-cluster) picks up the
#    ExternalSecret and creates/updates the testpilot-secrets Secret:
kubectl apply -k infra/k8s/overlays/production/
# 4. Verify ESO actually synced it:
kubectl -n testpilot-production get externalsecret testpilot-secrets
kubectl -n testpilot-production describe externalsecret testpilot-secrets   # SecretSynced condition
```

**Validation note**: `kubeconform`'s built-in schemas cover core Kubernetes resources only, not
CRDs like `ExternalSecret` — validating it needs an extra schema source. Confirmed working:

```sh
cat infra/k8s/overlays/production/external-secret.yaml.example | docker run --rm -i ghcr.io/yannh/kubeconform:latest \
  -strict -summary \
  -schema-location default \
  -schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json'
# stdin - ExternalSecret testpilot-secrets is valid
```

This is a separate, explicit validation step from the main overlay's own `kubeconform` run above
(step 10's "Validating locally") — `external-secret.yaml.example` is not part of `resources:` by
default, so the main overlay's validation neither depends on nor covers it.

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

## The staging overlay (`overlays/staging/`)

Structurally identical to `overlays/production/` above — same `base/`, same kind of patches
(`config-patch.yaml`, `ingress-patch.yaml`), same `secretGenerator`-or-`ExternalSecret` choice —
just with staging's own values instead of production's. `overlays/production/` is **completely
unaffected** by this overlay's existence: nothing under it was edited to add staging.

| File | Contents |
|---|---|
| `overlays/staging/kustomization.yaml` | `resources: [../../base, namespace.yaml]`, `namespace: testpilot-staging`, the `images:` digest-pin transformer, the two `patches:`, and the `secretGenerator`. |
| `overlays/staging/namespace.yaml` | A `Namespace` resource named `testpilot-staging` — the actual isolation boundary from `overlays/production`'s `testpilot-production` (see below). |
| `overlays/staging/config-patch.yaml` | Overrides `testpilot-config`'s `ENVIRONMENT` (to `"staging"` — a real, explicitly-supported `Settings.environment` value, not `"production"`) and `CORS_ALLOWED_ORIGINS`. |
| `overlays/staging/ingress-patch.yaml` | Same JSON6902 shape as production's — different host, different TLS Secret name. |
| `overlays/staging/secrets.env.example` | Committed template, same 10 keys as production's — staging's own values, never copied from production's. |
| `overlays/staging/external-secret.yaml.example` | Same ESO alternative as production's (see "External Secrets Operator (alternative)" above) — staging's own remote-secret-path prefix (`testpilot/staging/...`). |

### How staging differs from production

Every one of these is a deliberate, distinct value — not an oversight if you notice they don't
match `overlays/production/`'s:

| | Production | Staging |
|---|---|---|
| Namespace | `testpilot-production` | `testpilot-staging` |
| Hostname | `testpilot.example.com` | `staging.testpilot.example.com` |
| `CORS_ALLOWED_ORIGINS` | matches production host | matches staging host |
| `ENVIRONMENT` (ConfigMap) | `"production"` (`base/config.yaml`'s own default, unpatched) | `"staging"` (patched) |
| TLS Secret name | `testpilot-tls` | `testpilot-staging-tls` |
| Image digest | last **independently re-verified** commit (pulled from GHCR, exercised with a real `PlaywrightEngine.load_page()` call) | last commit whose `docker-images` CI job was confirmed green (not separately re-pulled/tested by hand) — staging is meant to track whatever you're currently testing |
| `secrets.env`/`ExternalSecret` remote paths | `testpilot/production/...` | `testpilot/staging/...` |

**What's identical**: the application architecture — same `base/` Deployments, Services, and
Ingress path routing; same replica counts, resource requests/limits, and liveness/readiness
probes (verified: diffed the rendered output of `base/` directly against staging's, byte-for-byte
identical on every probe/resource/replica field — nothing was silently changed); same image
*names* (`testpilot-api`/`-worker`/`-frontend` remapped to the same GHCR repository, just a
different digest); same secrets mechanism choice (Option A `secretGenerator` by default, Option B
`ExternalSecret` available the same opt-in way).

### Configuring the staging overlay

Same six steps as "Configuring the production overlay" above, applied to `overlays/staging/`'s
own files instead:

1. **Domain**: replace `staging.testpilot.example.com` in **both**
   `overlays/staging/ingress-patch.yaml`'s host/TLS fields **and**
   `overlays/staging/config-patch.yaml`'s `CORS_ALLOWED_ORIGINS` — keep them in sync with each
   other, and distinct from whatever `overlays/production/` uses.
2. **Ingress controller**: `overlays/staging/ingress-patch.yaml`'s `ingressClassName: nginx` —
   same swap-if-needed note as production's.
3. **TLS**: same two shapes (cert-manager or a pre-existing Secret) as production — but staging's
   own `testpilot-staging-tls` Secret name and (if using cert-manager) potentially a different,
   lower-trust `ClusterIssuer` (e.g. a staging CA / Let's Encrypt staging environment, rather than
   production's real-cert issuer) — that choice is yours; this overlay only sets the placeholder.
4. **Public object storage endpoint** — same presigned-URL requirement as production (see
   `overlays/staging/secrets.env.example`'s own comment): staging needs its **own** bucket/
   endpoint, not production's — reusing production's here would mean staging traffic can read/
   write real production artifacts.
5. **Secrets**: `cp overlays/staging/secrets.env.example overlays/staging/secrets.env`, fill in
   **staging's own** values (gitignored, same `infra/k8s/overlays/*/secrets.env` pattern covers
   this directory too — see `.gitignore`). Or use the ESO alternative
   (`overlays/staging/external-secret.yaml.example`) the same opt-in way documented above for
   production. **Never reuse a production credential for staging** — see the isolation note below.
6. **Image tag for a specific commit**: same `docker buildx imagetools inspect` /
   `kustomize edit set image` commands as production's step 6, run from `infra/k8s/overlays/staging/`.

### Deploying and verifying

```sh
# Render only (no cluster needed):
kubectl kustomize infra/k8s/overlays/staging/

# Apply to a real cluster (requires secrets.env / an external-secrets
# mechanism already set up per step 5 above):
kubectl apply -k infra/k8s/overlays/staging/

# Verify the rollout:
kubectl -n testpilot-staging get pods -w
kubectl -n testpilot-staging rollout status deployment/testpilot-api
kubectl -n testpilot-staging rollout status deployment/testpilot-worker
kubectl -n testpilot-staging rollout status deployment/testpilot-frontend
kubectl -n testpilot-staging get ingress testpilot-ingress
curl https://staging.testpilot.example.com/api/v1/readyz   # {"status":"ok","checks":{"database":"ok","redis":"ok"}}
```

### Validating locally (no cluster required)

```sh
kubectl kustomize infra/k8s/overlays/staging/

cp infra/k8s/overlays/staging/secrets.env.example infra/k8s/overlays/staging/secrets.env
kubectl kustomize infra/k8s/overlays/staging/ | docker run --rm -i ghcr.io/yannh/kubeconform:latest -summary -strict
rm infra/k8s/overlays/staging/secrets.env   # never leave this behind
```

### Resource isolation from production

Verified directly (not just asserted) when this overlay was created: rendering both overlays and
diffing them confirms every one of the following differs between `overlays/production/` and
`overlays/staging/` — namespace, Ingress hostname, `CORS_ALLOWED_ORIGINS`, TLS Secret name, and
image digest — while every Kubernetes object name (`testpilot-config`, `testpilot-secrets`,
`testpilot-api`, etc.) stays the *same* name in *both*, which is exactly what makes namespace the
real isolation boundary: two same-named objects in two different namespaces are two entirely
separate Kubernetes objects, never the same one. The one thing this repo cannot verify for you:
that the *values* you put in `overlays/staging/secrets.env` are genuinely staging's own
credentials and not copy-pasted from production's — no namespace boundary protects against that.

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
