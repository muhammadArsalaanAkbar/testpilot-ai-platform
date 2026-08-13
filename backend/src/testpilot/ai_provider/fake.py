"""In-memory fake LLMProvider adapter (contracts/ai-provider-adapter.md).

Used for every `ai_generation`/`ai_analysis` unit/integration test (and as
the default `AI_PROVIDER=fake` runtime adapter in dev/test environments) so
those tests never depend on network access or a real provider. This is a
real, deterministic implementation of the Protocol — not a mock — its output
is derived entirely from the given context, exactly as a real provider's
would be, just without an actual model call.
"""

from __future__ import annotations

from typing import Literal

from testpilot.ai_provider.base import (
    AIProviderError,
    ChatContext,
    ChatResponse,
    FailureAnalysis,
    FailureContext,
    FormSnapshot,
    GeneratedTestCase,
    GeneratedTestCaseBatch,
    GeneratedTestStep,
    PageSnapshot,
    SiteAnalysisContext,
)

FailMode = Literal["none", "timeout", "malformed"]


def _valid_value_for(field_type: str) -> str:
    return {
        "email": "user@example.com",
        "password": "correct horse battery staple",
        "number": "42",
        "tel": "+15555550123",
    }.get(field_type, "sample text")


def _page_load_case(page: PageSnapshot) -> GeneratedTestCase:
    label = page.title or page.url
    return GeneratedTestCase(
        title=f"Verify {label} loads successfully",
        description=f"Confirms the {label} page is reachable and displays its expected content.",
        priority="medium",
        severity="minor",
        flow_type="positive",
        steps=[
            GeneratedTestStep(action_type="navigate", target_descriptor=page.url),
            GeneratedTestStep(action_type="assert_content", expected_assertion=page.title or label),
        ],
    )


def _form_cases(page: PageSnapshot, form: FormSnapshot) -> list[GeneratedTestCase]:
    label = page.title or page.url
    form_label = form.action or "the form"
    fields = form.fields or []

    positive = GeneratedTestCase(
        title=f"Submit {form_label} with valid input on {label}",
        description=f"Confirms {form_label} on {label} accepts valid input and completes successfully.",
        priority="high",
        severity="major",
        flow_type="positive",
        steps=[
            GeneratedTestStep(action_type="navigate", target_descriptor=page.url),
            *[
                GeneratedTestStep(
                    action_type="type", target_descriptor=field.name, input_value=_valid_value_for(field.field_type)
                )
                for field in fields
            ],
            GeneratedTestStep(action_type="submit", target_descriptor=form_label),
            GeneratedTestStep(action_type="assert_content", expected_assertion="success"),
        ],
    )
    negative = GeneratedTestCase(
        title=f"Submit {form_label} with invalid input on {label}",
        description=f"Confirms {form_label} on {label} rejects invalid input with a clear, visible error.",
        priority="high",
        severity="major",
        flow_type="negative",
        steps=[
            GeneratedTestStep(action_type="navigate", target_descriptor=page.url),
            *[
                GeneratedTestStep(action_type="type", target_descriptor=field.name, input_value="not-valid!!")
                for field in fields
            ],
            GeneratedTestStep(action_type="submit", target_descriptor=form_label),
            GeneratedTestStep(action_type="assert_content", expected_assertion="error"),
        ],
    )
    edge = GeneratedTestCase(
        title=f"Submit {form_label} with empty input on {label}",
        description=f"Confirms {form_label} on {label} handles empty/boundary input without crashing.",
        priority="medium",
        severity="minor",
        flow_type="edge_case",
        steps=[
            GeneratedTestStep(action_type="navigate", target_descriptor=page.url),
            *[GeneratedTestStep(action_type="type", target_descriptor=field.name, input_value="") for field in fields],
            GeneratedTestStep(action_type="submit", target_descriptor=form_label),
            GeneratedTestStep(action_type="assert_content", expected_assertion="required"),
        ],
    )
    return [positive, negative, edge]


class FakeLLMProvider:
    """Deterministic in-memory `LLMProvider` (satisfies the Protocol structurally)."""

    provider_name = "fake"
    model = "fake-deterministic"

    def __init__(self, *, fail_mode: FailMode = "none") -> None:
        self.fail_mode = fail_mode

    async def generate_test_cases(self, context: SiteAnalysisContext) -> GeneratedTestCaseBatch:
        if self.fail_mode == "timeout":
            raise AIProviderError("Simulated provider timeout", retryable=True)
        if self.fail_mode == "malformed":
            raise AIProviderError("Simulated malformed provider output", retryable=False)

        test_cases: list[GeneratedTestCase] = []
        for page in context.pages:
            test_cases.append(_page_load_case(page))
            for form in page.forms:
                test_cases.extend(_form_cases(page, form))

        return GeneratedTestCaseBatch(test_cases=test_cases, tokens_used=len(test_cases) * 50)

    async def analyze_failure(self, context: FailureContext) -> FailureAnalysis:
        if self.fail_mode == "timeout":
            raise AIProviderError("Simulated provider timeout", retryable=True)
        if self.fail_mode == "malformed":
            raise AIProviderError("Simulated malformed provider output", retryable=False)

        expected = context.step_expected_assertion or "the expected outcome"
        return FailureAnalysis(
            explanation=(
                f"The '{context.step_action_type}' step did not produce the expected outcome. "
                f"Actual observed state: {context.actual_state}"
            ),
            root_cause="The application did not reach the expected state before the assertion ran.",
            severity="major",
            suggested_fix="Review the application's response for this step and confirm the expected assertion is still accurate.",
            expected_vs_actual=f"Expected: {expected}. Actual: {context.actual_state}",
        )

    async def chat(self, context: ChatContext) -> ChatResponse:
        if self.fail_mode == "timeout":
            raise AIProviderError("Simulated provider timeout", retryable=True)
        if self.fail_mode == "malformed":
            raise AIProviderError("Simulated malformed provider output", retryable=False)

        last_user_message = next((m.content for m in reversed(context.messages) if m.role == "user"), "")
        return ChatResponse(
            message=f"(fake assistant) I received your message: {last_user_message!r}",
            grounded=context.grounding_data is not None,
        )
