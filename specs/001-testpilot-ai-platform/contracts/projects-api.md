# Contract: Projects API

See `_conventions.md`. Covers FR-025–FR-035.

| Method & Path | Auth | Request | Response | Errors |
|---|---|---|---|---|
| `GET /projects` | Authenticated | `?status=active\|archived` | `200 {items: [Project]}` | — |
| `POST /projects` | Authenticated | `{name, url, settings?}` | `201 {project}` | `422 invalid_url`, `422 url_not_public` (SSRF guard, FR-035), `402 plan_limit_exceeded` |
| `GET /projects/{id}` | Authenticated | — | `200 {project, recent_runs: [TestRunSummary]}` | `404` |
| `PATCH /projects/{id}` | Authenticated | `{name?, url?, settings?}` | `200 {project}` | `404`, `422` |
| `POST /projects/{id}/archive` | Authenticated | — | `200 {project}` (idempotent) | `404` |
| `POST /projects/{id}/unarchive` | Authenticated | — | `200 {project}` | `404` |
| `DELETE /projects/{id}` | Authenticated | `{confirm: true}` | `204` (hard delete, cascades per data-model.md) | `404`, `422 confirmation_required` |

**Project object shape**: `{id, name, url, status, settings, created_at, updated_at}`.

**Validation** (FR-026, FR-035, FR-032): URL is checked for well-formedness and rejected if it
resolves to a private/loopback/link-local/reserved range. Creating a test run or triggering AI
generation against an `archived` project returns `409 project_archived` from the respective
endpoint (not this one).
