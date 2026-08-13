# Contract: Test Cases API

See `_conventions.md`. Covers FR-036–FR-058 (AI generation + library management).

| Method & Path | Auth | Request | Response | Errors |
|---|---|---|---|---|
| `GET /projects/{project_id}/test-cases` | Authenticated | `?status=&priority=&severity=&tag=&source=&q=&sort=` | `200 {items: [TestCase]}` (paginated) | `404` project |
| `POST /projects/{project_id}/test-cases` | Authenticated | `{title, description, priority, severity, tags, steps: [TestStep]}` | `201 {test_case}` (source=`manual`) | `409 project_archived`, `422` |
| `GET /projects/{project_id}/test-cases/{id}` | Authenticated | — | `200 {test_case, steps: [TestStep], recent_results: [TestResultSummary]}` | `404` |
| `PATCH /projects/{project_id}/test-cases/{id}` | Authenticated | `{title?, description?, priority?, severity?, tags?, steps?}` | `200 {test_case}` | `404`, `422` |
| `POST /projects/{project_id}/test-cases/{id}/approve` | Authenticated | — | `200 {test_case}` (status→approved) | `404` |
| `POST /projects/{project_id}/test-cases/{id}/reject` | Authenticated | — | `200 {test_case}` (status→rejected) | `404` |
| `DELETE /projects/{project_id}/test-cases/{id}` | Authenticated | — | `204` | `404` |
| `POST /projects/{project_id}/test-cases/generate` | Authenticated | `{}` (uses project settings) | `202 {generation_run}` | `409 generation_in_progress` (FR-047), `402 plan_limit_exceeded`, `409 project_archived` |
| `GET /projects/{project_id}/test-cases/generate/{generation_run_id}` | Authenticated | — | `200 {generation_run: {id, status, failure_reason?, created_test_case_ids?}}` | `404` |
| `POST /projects/{project_id}/test-cases/{id}/regenerate` | Authenticated | — | `202 {generation_run}` (scope=`single_case`) | `409`, `402`, `404` |

**TestCase object shape**: `{id, project_id, title, description, priority, severity, status,
source, tags, last_result, created_at, updated_at}`. `TestStep`:
`{order_index, action_type, target_descriptor, input_value, expected_assertion}`.

**Generation polling contract**: `generation_run.status` transitions
`queued → running → completed | failed`, matching plan.md's Async Job Lifecycle. On `completed`,
`created_test_case_ids` lists the new `draft` test cases for the frontend to fetch and route the
user into the review flow (`/test-cases/generate` review queue).
