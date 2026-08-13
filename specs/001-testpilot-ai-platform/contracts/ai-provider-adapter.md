# Contract: `LLMProvider` Internal Interface

The provider-agnostic boundary required by NFR-018/INT-002. Every concrete AI adapter (the
initially-configured cloud provider, and any later swap) MUST satisfy this Protocol. Callers
(`ai_generation`, `ai_analysis`, and the Future `assistant` library) depend only on this
interface, never on a specific provider's SDK types.

## Operations

### `generate_test_cases(context: SiteAnalysisContext) -> GeneratedTestCaseBatch`

- **Input** (`SiteAnalysisContext`): project name/URL, a bounded structured extraction of
  reachable public pages (titles, headings, forms and their fields, interactive elements,
  navigation links) — never raw full-page HTML — plus any project-level generation preferences
  (FR-031).
- **Output** (`GeneratedTestCaseBatch`): a list of structured test cases, each with `title`,
  `description` (purpose explanation, FR-038), `priority`, `severity`, `flow_type`
  (`positive`|`negative`|`edge_case`, so the caller can verify FR-039/FR-040 coverage), and an
  ordered list of steps (`action_type`, `target_descriptor`, `input_value`,
  `expected_assertion`) matching the `test_steps` shape in data-model.md.
- **Contract**: output MUST be structured/schema-validated by the adapter (via the provider's
  tool-use/JSON-mode capability) — the adapter, not the caller, is responsible for never
  returning free-text the caller would have to parse. On provider error/timeout/malformed
  output after the adapter's own internal retry, the adapter raises a typed
  `AIProviderError` (never returns a partially-valid batch) so the caller can apply FR-046's
  bounded-retry-then-fail-clean policy at the job level.

### `analyze_failure(context: FailureContext) -> FailureAnalysis`

- **Input** (`FailureContext`): the failing `TestStep`'s action/target/expected assertion, the
  actual observed state/error text, the ordered execution log up to the failure, and a
  reference to the failure screenshot (passed as a provider-appropriate image input, e.g. a
  signed URL or base64 payload depending on adapter capability — the caller does not need to
  know which).
- **Output** (`FailureAnalysis`): `explanation`, `root_cause`, `severity`, `suggested_fix`, all
  plain-language/developer-facing per FR-081, plus an explicit restatement of expected-vs-actual
  (FR-082) so the caller can render it without re-deriving it from raw fields.
- **Contract**: same structured-output and typed-error requirements as `generate_test_cases`.

### `chat(context: ChatContext) -> ChatResponse` *(Future — AI QA Assistant, FR-097–FR-103)*

- **Input** (`ChatContext`): conversation history (this session only) + optional grounding data
  (project's recent test/issue summary, assembled by the `assistant` library — never the raw
  full dataset) when the question is project-scoped.
- **Output** (`ChatResponse`): `message`, plus `grounded: bool` and `referenced_entities: []`
  (FR-102's citation requirement) when grounding data was used.
- **Status**: interface reserved now so `ai_provider` adapters implement all three methods from
  the start (avoiding an interface-breaking change later); the `assistant` caller library itself
  is Future work, not built at MVP.

## Adapter responsibilities (every implementation)

1. Never receive or transmit data outside the requesting Organization's own scope — the adapter
   trusts its caller for this (SEC-012 is enforced by `ai_generation`/`ai_analysis` assembling
   only in-scope context), but MUST NOT itself cache/log full request payloads beyond what
   `research.md`'s observability decisions call for (correlation ID, not full content, in logs).
2. Enforce a request timeout matching FR-046/FR-083's bounded-retry policy; never hang
   indefinitely.
3. Report token/cost usage in a way `ai_generation`/`ai_analysis` can attribute to
   `usage_records(metric=ai_operations)` for plan-limit enforcement (FR-123).

## Testing contract (constitution Integration Testing principle)

Every adapter has a contract test suite run against a shared fixture set (a handful of
representative `SiteAnalysisContext`/`FailureContext` inputs) asserting: valid structured output
shape, typed error raised on injected timeout/malformed-response conditions, and no
Organization-scope leakage in constructed prompts. A fake in-memory adapter implementing this
same Protocol is used for all `ai_generation`/`ai_analysis` unit tests, so those tests never
depend on network access or a real provider.
