# Contract: `BrowserAutomationEngine` Internal Interface

The extensibility boundary required by FR-068/NFR-019. Playwright is the only implementation at
MVP; this contract exists so a second engine could be added without any change to
`TestCase`/`TestStep`/`TestResult` or to the `execution` orchestrator that calls this interface.

## Operations

### `run_test_case(test_case: TestCase, steps: list[TestStep], target_url: str) -> TestResult`

- Creates one isolated browser session (Playwright: a fresh `BrowserContext` from a pre-warmed
  `Browser`, per `research.md` #6) for the full duration of this one test case (FR-067).
- Executes `steps` in `order_index` order, calling the step-executor primitive matching each
  step's `action_type` (below).
- Enforces a per-step timeout and an overall per-test-case timeout (FR-066) internally — the
  caller does not implement timeout logic itself.
- Captures a screenshot automatically on the step that fails (FR-064); captures additional
  checkpoint screenshots for any step explicitly flagged for one.
- Returns a fully-populated `TestResult` (status, execution_log, failure_step_index,
  error_message, duration_ms) plus the list of captured artifact bytes/references for the caller
  to hand to `storage.save_artifact(...)` — this interface does not talk to object storage
  directly, keeping storage a separate, swappable concern.
- On an internal crash (browser process/context failure), returns a `TestResult(status=error,
  error_message=...)` rather than raising an unhandled exception past this boundary — the
  orchestrator's per-case fault isolation (NFR-007/FR-075) depends on this method never
  propagating a raw engine exception to the run loop.

## Step-executor primitives (one per `TestStep.action_type`, FR-059–FR-063)

| `action_type` | Behavior |
|---|---|
| `navigate` | Load `target_descriptor` (a URL or relative path) in the current context |
| `click` | Locate the element described by `target_descriptor` and click it |
| `type` | Locate the element and enter `input_value` |
| `submit` | Submit the form containing/associated with `target_descriptor` |
| `assert_url` | Compare current page URL against `expected_assertion` (exact or pattern) |
| `assert_content` | Assert `expected_assertion` text is visible on the page |
| `assert_element` | Assert the element at `target_descriptor` is present/absent/in the state described by `expected_assertion` |

Adding a new `action_type` in the future means adding one new executor function matching this
table's shape — it does not require changing `run_test_case`'s signature or the `TestResult`
shape (FR-068).

## Isolation & safety contract

- The engine MUST call the shared `validate_public_url()` guard (SEC-006/FR-135) immediately
  before the initial `navigate` of every test case — even though the caller (worker job) already
  validated the project URL at run-enqueue time, this is a mandatory re-check inside the engine
  boundary itself, since the engine is the actual point of outbound network access.
- No two test cases in the same or different concurrent runs may share a `BrowserContext`
  (FR-067) — the engine allocates a new context per `run_test_case` call, never reuses one
  across calls.

## Testing contract (constitution Integration Testing principle)

A fixture-page test suite (a small static site served locally in CI) exercises every
`action_type` against known, stable markup — this is what actually proves FR-059–FR-064 rather
than trusting Playwright's own test suite. A second suite intentionally exercises failure paths
(missing element, navigation timeout, browser-context crash simulation) to prove
`run_test_case` returns a structured `error`/`failed` result rather than raising, satisfying
NFR-007's fault-isolation requirement at the unit-contract level before it's ever exercised at
the full orchestrator level.
