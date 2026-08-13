# Contract: Test Runs & Results API

See `_conventions.md`. Covers FR-069–FR-086 (execution + AI failure analysis).

| Method & Path | Auth | Request | Response | Errors |
|---|---|---|---|---|
| `GET /projects/{project_id}/test-runs` | Authenticated | `?page=` | `200 {items: [TestRunSummary]}` | `404` project |
| `POST /projects/{project_id}/test-runs` | Authenticated | `{test_case_ids: [uuid]}` | `202 {test_run}` (status=`queued`) | `409 project_archived`, `402 plan_limit_exceeded`, `422 no_approved_cases_selected` (rejects any `rejected`-status case, FR-057) |
| `GET /projects/{project_id}/test-runs/{id}` | Authenticated | — | `200 {test_run, results: [TestResultSummary]}` | `404` |
| `POST /projects/{project_id}/test-runs/{id}/retry-failed` | Authenticated | — | `202 {test_run}` — a **new** test_run scoped to the previous run's failed case IDs (FR-073) | `404`, `409 run_not_completed` |
| `GET /projects/{project_id}/test-runs/{run_id}/results/{result_id}` | Authenticated | — | `200 {test_result, execution_log, artifacts: [{type, url, captured_at}], ai_analyses: [AIAnalysis]}` | `404` |
| `POST /projects/{project_id}/test-runs/{run_id}/results/{result_id}/analyze` | Authenticated | — | `202 {ai_analysis}` (status=`queued`→poll same resource) | `409 result_not_failed`, `402 plan_limit_exceeded` |
| `GET /projects/{project_id}/test-runs/{run_id}/results/{result_id}/analyses/{analysis_id}` | Authenticated | — | `200 {ai_analysis}` | `404` |

**TestRun object shape**: `{id, project_id, status, summary_total, summary_passed,
summary_failed, summary_skipped, started_at, completed_at, created_at}`. Frontend polls this
resource (or the list) while `status` is `queued`/`running` (Research #11).

**TestResult object shape**: `{id, test_run_id, test_case_id, status, failure_step_index,
error_message, started_at, completed_at, duration_ms}`.

**AIAnalysis object shape**: `{id, status, explanation, root_cause, severity, suggested_fix,
provider, model, created_at}` when `status=completed`; `{id, status: "failed",
failure_reason}` otherwise (FR-083 — never a fabricated placeholder body).
