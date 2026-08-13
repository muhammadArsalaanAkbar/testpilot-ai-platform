# Contract: Reports & Analytics API

See `_conventions.md`. Covers FR-104–FR-111.

| Method & Path | Auth | Request | Response | Errors |
|---|---|---|---|---|
| `GET /projects/{project_id}/reports/summary` | Authenticated | `?from=&to=` (ISO dates, default last 30 days) | `200 {total, passed, failed, skipped, pass_percentage, failure_percentage, coverage_percentage}` | `404` project |
| `GET /projects/{project_id}/reports/issues-by-severity` | Authenticated | `?from=&to=` | `200 {minor, major, critical, blocker}` (counts) | `404` |
| `GET /projects/{project_id}/reports/run-history` | Authenticated | `?page=` | `200 {items: [TestRunSummary]}` (same shape as test-runs list, surfaced here for the Reports page) | `404` |
| `GET /projects/{project_id}/reports/trend` *(Future)* | Authenticated | `?from=&to=&granularity=day\|week` | `200 {items: [{date, pass_rate}]}` | `404` |
| `GET /organizations/current/reports/rollup` *(Future)* | Authenticated | — | `200 {projects: [{project_id, pass_percentage, open_issues}]}` | — |

**Computation note** (plan.md Reports & Analytics Architecture): MVP responses are computed
on-read from `test_runs`/`test_results`/`issues` filtered by `organization_id` + `project_id` +
date range, using `test_runs.summary_*` counters to avoid re-scanning every `test_result` row for
totals. `coverage_percentage` = distinct approved test cases with ≥1 result in range ÷ total
approved test cases (FR-105).
