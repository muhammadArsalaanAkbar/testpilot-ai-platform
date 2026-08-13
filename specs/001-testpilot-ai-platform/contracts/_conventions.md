# API Contract Conventions

Applies to every contract file in this directory unless a specific endpoint overrides it.

- **Base path**: `/api/v1`
- **Auth**: `Authenticated` means a valid access token (Bearer header, issued from the refresh
  cookie flow) resolving a `current_user` + `current_organization`, per plan.md's
  Authentication architecture. `Public` means no auth required.
- **Content type**: `application/json` for all request/response bodies except artifact binary
  retrieval, which returns a redirect to a signed storage URL (see `_storage-note` below).
- **Pagination**: list endpoints accept `?page=1&page_size=25` (default 25, max 100) and return
  `{"items": [...], "page": N, "page_size": N, "total": N}`.
- **Errors**: every non-2xx response body is `{"error": {"code": "string", "message": "string",
  "details": {}}}`. `code` is a stable machine-readable string (e.g.
  `plan_limit_exceeded`, `ai_analysis_unavailable`, `not_found`) the frontend switches on;
  `message` is human-readable fallback text.
- **Not-found vs. forbidden**: per FR-138/SEC-011, a resource that exists but belongs to another
  Organization returns the same `404 {"error": {"code": "not_found"}}` as a resource that does
  not exist at all. There is no `403` for cross-tenant access anywhere in this API.
- **Async operations**: any endpoint that starts a background job returns `202 Accepted` with a
  job-resource body (`{"id", "status": "queued"}`); the client polls the corresponding `GET`
  endpoint for that job resource until it reaches a terminal `status`.
- **Idempotency**: `POST` endpoints that enqueue a job are not idempotent by design (each call
  creates a new job); destructive `DELETE`/archive endpoints are idempotent (repeating the call
  on an already-archived/deleted resource is a no-op `200`, not an error).
- **Artifact URLs** (`_storage-note`): any field named `*_url` for a screenshot/log (e.g. a
  `TestResult`'s artifact list) is a short-lived signed URL generated at response time, never a
  permanent public link.
