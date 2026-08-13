# Contract: Issues (Bugs) API

See `_conventions.md`. Covers FR-087–FR-096.

| Method & Path | Auth | Request | Response | Errors |
|---|---|---|---|---|
| `GET /projects/{project_id}/issues` | Authenticated | `?status=&severity=&priority=` | `200 {items: [Issue]}` | `404` project |
| `POST /projects/{project_id}/issues` | Authenticated | `{title, description, severity, priority}` | `201 {issue}` (manual, FR-088) | `422` |
| `POST /projects/{project_id}/issues/from-result/{result_id}` | Authenticated | `{title?, description?, severity, priority}` (title/description default from the failure, editable) | `201 {issue}` (pre-linked + attachments copied, FR-087) | `404 result_not_found`, `422` |
| `GET /projects/{project_id}/issues/{id}` | Authenticated | — | `200 {issue, attachments: [{type, url}], source_test_case, source_test_run}` | `404` |
| `PATCH /projects/{project_id}/issues/{id}` | Authenticated | `{title?, description?, severity?, priority?, status?, assignee_user_id?}` | `200 {issue}` | `404`, `422` |
| `POST /projects/{project_id}/issues/{id}/attachments` | Authenticated | multipart file or `{storage_key}` from an existing artifact | `201 {attachment}` | `404`, `422 file_too_large` |

**Issue object shape**: `{id, project_id, title, description, severity, priority, status,
assignee_user_id, source_test_case_id, source_test_run_id, created_by_user_id, created_at,
updated_at}`.

**Status lifecycle**: `open → in_progress → resolved → closed`, or `open/in_progress →
wont_fix`. All transitions are valid from any non-terminal state except `closed`/`wont_fix`,
which require re-opening to `open` explicitly rather than direct transition to another
non-open state.
