# Contract: Notifications API

See `_conventions.md`. Covers FR-114–FR-118.

| Method & Path | Auth | Request | Response | Errors |
|---|---|---|---|---|
| `GET /notifications` | Authenticated | `?unread_only=true\|false&page=` | `200 {items: [Notification], unread_count}` | — |
| `POST /notifications/{id}/read` | Authenticated | — | `200 {notification}` (idempotent) | `404` |
| `POST /notifications/read-all` | Authenticated | — | `204` | — |

**Notification object shape**: `{id, type, related_entity_type, related_entity_id, read_at,
created_at}`. The frontend resolves `related_entity_type`/`related_entity_id` into a route (e.g.
`test_run` → `/projects/{project_id}/test-runs/{id}`) using a small client-side lookup table —
the API does not embed a pre-built URL, keeping the contract stable if frontend routes change.

Recipients and trigger conditions are exactly the events in spec.md's Notifications section
(run completion, critical failure, AI analysis completion) — this contract only covers how the
frontend *reads* notifications; creation happens server-side in the `execution`/`ai_analysis`
worker jobs per plan.md, not via a public "create notification" endpoint.
