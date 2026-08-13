"""Unit tests for the fake LLMProvider adapter's structured-output contract
(T109, contracts/ai-provider-adapter.md's Testing contract): valid structured
output shape, typed error on injected timeout/malformed conditions, and that
output only ever reflects the given context (no foreign/leaked data).
"""

import pytest

from testpilot.ai_provider.base import (
    AIProviderError,
    FormFieldSnapshot,
    FormSnapshot,
    PageSnapshot,
    SiteAnalysisContext,
)
from testpilot.ai_provider.fake import FakeLLMProvider

pytestmark = pytest.mark.anyio


def _page_with_form() -> PageSnapshot:
    return PageSnapshot(
        url="https://example.com/signup",
        title="Sign Up",
        headings=["Create your account"],
        forms=[
            FormSnapshot(
                action="/signup",
                method="post",
                fields=[
                    FormFieldSnapshot(name="email", field_type="email", label="Email"),
                    FormFieldSnapshot(name="password", field_type="password", label="Password"),
                ],
            )
        ],
        interactive_elements=["Sign up"],
        links=["https://example.com/login"],
    )


def _page_without_form() -> PageSnapshot:
    return PageSnapshot(
        url="https://example.com/about",
        title="About Us",
        headings=["Our mission"],
        forms=[],
        interactive_elements=[],
        links=[],
    )


async def test_generate_test_cases_returns_structured_batch():
    provider = FakeLLMProvider()
    context = SiteAnalysisContext(
        project_name="Example App", project_url="https://example.com", pages=[_page_with_form()]
    )

    batch = await provider.generate_test_cases(context)

    assert len(batch.test_cases) > 0
    for case in batch.test_cases:
        assert case.title
        assert case.description
        assert case.priority in {"low", "medium", "high", "critical"}
        assert case.severity in {"minor", "major", "critical", "blocker"}
        assert case.flow_type in {"positive", "negative", "edge_case"}
        assert len(case.steps) > 0
        for step in case.steps:
            assert step.action_type in {
                "navigate",
                "click",
                "type",
                "submit",
                "assert_url",
                "assert_content",
                "assert_element",
            }


async def test_generate_test_cases_produces_positive_negative_and_edge_case_for_a_form():
    """FR-039/FR-040: a page with a form yields both positive and negative
    cases, plus at least one edge case for that flow."""
    provider = FakeLLMProvider()
    context = SiteAnalysisContext(
        project_name="Example App", project_url="https://example.com", pages=[_page_with_form()]
    )

    batch = await provider.generate_test_cases(context)
    flow_types = {case.flow_type for case in batch.test_cases}

    assert "positive" in flow_types
    assert "negative" in flow_types
    assert "edge_case" in flow_types


async def test_generate_test_cases_gives_every_case_a_non_empty_purpose_explanation():
    provider = FakeLLMProvider()
    context = SiteAnalysisContext(
        project_name="Example App",
        project_url="https://example.com",
        pages=[_page_with_form(), _page_without_form()],
    )

    batch = await provider.generate_test_cases(context)

    for case in batch.test_cases:
        assert case.description.strip() != ""


async def test_generate_test_cases_only_reflects_the_given_context():
    """No foreign/leaked data (contract: adapters MUST NOT leak data outside
    the requesting scope) — every generated case must reference only URLs
    and titles that were actually present in the input context."""
    provider = FakeLLMProvider()
    page = _page_without_form()
    context = SiteAnalysisContext(project_name="Example App", project_url="https://example.com", pages=[page])

    batch = await provider.generate_test_cases(context)

    for case in batch.test_cases:
        for step in case.steps:
            if step.target_descriptor:
                assert step.target_descriptor == page.url or step.target_descriptor in page.title


async def test_generate_test_cases_raises_typed_error_on_injected_timeout():
    provider = FakeLLMProvider(fail_mode="timeout")
    context = SiteAnalysisContext(project_name="Example App", project_url="https://example.com", pages=[])

    with pytest.raises(AIProviderError) as exc_info:
        await provider.generate_test_cases(context)
    assert exc_info.value.retryable is True


async def test_generate_test_cases_raises_typed_error_on_injected_malformed_output():
    provider = FakeLLMProvider(fail_mode="malformed")
    context = SiteAnalysisContext(project_name="Example App", project_url="https://example.com", pages=[])

    with pytest.raises(AIProviderError) as exc_info:
        await provider.generate_test_cases(context)
    assert exc_info.value.retryable is False


async def test_analyze_failure_returns_structured_analysis():
    from testpilot.ai_provider.base import FailureContext

    provider = FakeLLMProvider()
    context = FailureContext(
        step_action_type="assert_content",
        step_target_descriptor=None,
        step_expected_assertion="Welcome back",
        actual_state="Page showed 'Invalid credentials'",
        execution_log=["navigate /login", "type #email", "type #password", "submit", "assert_content failed"],
        screenshot_reference="s3://artifacts/failure.png",
    )

    analysis = await provider.analyze_failure(context)

    assert analysis.explanation.strip() != ""
    assert analysis.root_cause.strip() != ""
    assert analysis.severity in {"minor", "major", "critical", "blocker"}
    assert analysis.suggested_fix.strip() != ""
    assert analysis.expected_vs_actual.strip() != ""


async def test_chat_returns_a_response():
    from testpilot.ai_provider.base import ChatContext, ChatMessage

    provider = FakeLLMProvider()
    context = ChatContext(messages=[ChatMessage(role="user", content="What is TestPilot AI?")])

    response = await provider.chat(context)

    assert response.message.strip() != ""
    assert response.grounded is False


async def test_chat_reports_grounded_when_grounding_data_is_given():
    from testpilot.ai_provider.base import ChatContext, ChatMessage

    provider = FakeLLMProvider()
    context = ChatContext(
        messages=[ChatMessage(role="user", content="What's failing in this project?")],
        grounding_data={"open_issues": 3},
    )

    response = await provider.chat(context)

    assert response.grounded is True


async def test_chat_raises_typed_error_on_injected_timeout():
    from testpilot.ai_provider.base import ChatContext, ChatMessage

    provider = FakeLLMProvider(fail_mode="timeout")
    context = ChatContext(messages=[ChatMessage(role="user", content="hello")])

    with pytest.raises(AIProviderError) as exc_info:
        await provider.chat(context)
    assert exc_info.value.retryable is True


async def test_chat_raises_typed_error_on_injected_malformed_output():
    from testpilot.ai_provider.base import ChatContext, ChatMessage

    provider = FakeLLMProvider(fail_mode="malformed")
    context = ChatContext(messages=[ChatMessage(role="user", content="hello")])

    with pytest.raises(AIProviderError) as exc_info:
        await provider.chat(context)
    assert exc_info.value.retryable is False
