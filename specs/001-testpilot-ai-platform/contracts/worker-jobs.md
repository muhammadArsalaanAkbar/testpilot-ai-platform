# Contract: Background Job Payloads (Internal)

Not an HTTP API — this is the contract between the API process (producer) and worker processes
(consumers) across the Redis queues defined in plan.md (Research #5). Every job shares one
envelope so logging/tracing/retry handling is uniform across job types (plan.md's Background
Jobs & Worker Architecture).

## Shared envelope

```
{
  "job_id": uuid,          // == the polled resource's id (generation_run.id, test_run.id, ai_analysis.id)
  "organization_id": uuid,
  "requested_by_user_id": uuid,
  "correlation_id": string,   // propagated from the originating API request's correlation ID
  "enqueued_at": timestamp,
  "payload": { ... }          // job-type-specific, see below
}
```

## `ai-generation` queue — `GenerateTestCasesJob`

```
payload: {
  "generation_run_id": uuid,
  "project_id": uuid,
  "scope": "full_batch" | "single_case",
  "target_test_case_id": uuid | null   // set when scope == "single_case"
}
```

**Handler contract**: on start, set `generation_runs.status = running`. On success, persist new
`test_cases`/`test_steps` rows (`status=draft`, `source=ai_generated`), set
`generation_runs.status = completed`, write a `notifications` row for
`requested_by_user_id` (FR-116). On failure (provider error, timeout, malformed output after
bounded retries), set `generation_runs.status = failed` with `failure_reason` — never persists
partial/unreviewed test cases as if complete (FR-046).

## `test-execution` queue — `ExecuteTestRunJob`

```
payload: {
  "test_run_id": uuid,
  "project_id": uuid,
  "test_case_ids": [uuid]   // denormalized from test_run_cases at enqueue time
}
```

**Handler contract**: set `test_runs.status = running`, `started_at = now()`. For each
`test_case_id` in order: re-validate the project URL against the SSRF guard, run it via
`BrowserAutomationEngine.run_test_case(...)` (see `browser-automation-adapter.md`), persist a
`test_results` row, upload any captured artifacts immediately (not batched), update
`test_cases.last_result` and `test_runs.summary_*` counters. A single test case's engine-level
exception is caught and recorded as that case's `error` result (NFR-007/FR-075) — it does not
abort the job. On all cases processed, set `test_runs.status = completed`,
`completed_at = now()`, write a `notifications` row (`run_completed`, or `run_failed_critical`
additionally if any result was `critical` severity per an associated issue/analysis).

## `ai-analysis` queue — `AnalyzeFailureJob`

```
payload: {
  "ai_analysis_id": uuid,
  "test_result_id": uuid
}
```

**Handler contract**: assemble context (failing step, expected/actual, log excerpt, screenshot
reference — FR-080) scoped strictly to the result's own Organization (SEC-012), call
`LLMProvider.analyze_failure(...)` (see `ai-provider-adapter.md`), persist explanation/root
cause/severity/suggested fix on the `ai_analyses` row with `status=completed`, write a
`notifications` row (`ai_analysis_completed`). On failure, `status=failed` with
`failure_reason`, notification type `ai_analysis_failed` — the frontend distinguishes this from
"no analysis requested yet" (spec Edge Cases).

## Retry & idempotency (all queues)

- Bounded retry (2 attempts) with exponential backoff on transient errors (network timeout,
  provider 5xx/429). A permanent error (validation failure, resource deleted mid-flight) fails
  immediately without retry.
- Every handler's first action is to check the target row's current `status`; if it is already
  in a terminal state, the handler exits as a no-op (protects against at-least-once queue
  redelivery re-applying a completed job).
