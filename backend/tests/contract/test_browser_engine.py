"""Contract/fixture test: every step-executor action_type against a local
fixture page (T123, contracts/browser-automation-adapter.md, FR-059-FR-063).

Uses the local fixture site (tests/fixtures/fixture_site/) served by
tests/fixtures/server.py, not a third-party site — deterministic, no
external-network dependency.
"""

import uuid

import pytest

from testpilot.execution.playwright_engine import PlaywrightEngine
from testpilot.testcases.models import (
    TestCase,
    TestCasePriority,
    TestCaseSeverity,
    TestCaseSource,
    TestCaseStatus,
    TestStep,
    TestStepActionType,
)

pytestmark = pytest.mark.anyio


def _test_case() -> TestCase:
    return TestCase(
        organization_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        title="Fixture site walkthrough",
        description="Exercises every step-executor action_type.",
        priority=TestCasePriority.medium,
        severity=TestCaseSeverity.minor,
        status=TestCaseStatus.draft,
        source=TestCaseSource.manual,
    )


def _step(order_index: int, action_type: TestStepActionType, **kwargs: object) -> TestStep:
    return TestStep(
        organization_id=uuid.uuid4(),
        test_case_id=uuid.uuid4(),
        order_index=order_index,
        action_type=action_type,
        **kwargs,  # type: ignore[arg-type]
    )


async def _public_resolver(hostname: str) -> list[str]:
    # The fixture server binds to 127.0.0.1, which validate_public_url's real
    # DNS resolver would (correctly) reject — SEC-006's guard exists for
    # production targets, not local test infrastructure. This resolver is
    # injected only in tests, via the same Resolver mechanism
    # tests/unit/test_url_validation.py already exercises; production code
    # always uses PlaywrightEngine's default (real) resolver.
    return ["8.8.8.8"]  # same public stand-in test_url_validation.py uses


@pytest.fixture
async def engine():
    eng = PlaywrightEngine(url_resolver=_public_resolver)
    yield eng
    await eng.close()


async def test_navigate_step_loads_the_target_page(engine, fixture_site_url):
    steps = [_step(0, TestStepActionType.navigate, target_descriptor=f"{fixture_site_url}/about.html")]

    result, artifacts = await engine.run_test_case(_test_case(), steps, fixture_site_url)

    assert result.status == "passed"
    assert result.execution_log[0].status == "passed"
    assert artifacts == []


async def test_click_step_triggers_a_real_dom_update(engine, fixture_site_url):
    steps = [
        _step(0, TestStepActionType.navigate, target_descriptor=fixture_site_url),
        _step(1, TestStepActionType.click, target_descriptor="#counter-btn"),
        _step(2, TestStepActionType.assert_content, expected_assertion="1"),
    ]

    result, _artifacts = await engine.run_test_case(_test_case(), steps, fixture_site_url)

    assert result.status == "passed"
    assert [entry.status for entry in result.execution_log] == ["passed", "passed", "passed"]


async def test_type_and_submit_steps_complete_a_real_form_flow(engine, fixture_site_url):
    steps = [
        _step(0, TestStepActionType.navigate, target_descriptor=fixture_site_url),
        _step(1, TestStepActionType.type, target_descriptor="#email-input", input_value="user@example.com"),
        _step(2, TestStepActionType.type, target_descriptor="#password-input", input_value="hunter2"),
        _step(3, TestStepActionType.submit, target_descriptor="#login-submit"),
        _step(4, TestStepActionType.assert_url, expected_assertion="success.html"),
        _step(5, TestStepActionType.assert_content, expected_assertion="Welcome back"),
    ]

    result, _artifacts = await engine.run_test_case(_test_case(), steps, fixture_site_url)

    assert result.status == "passed"
    assert result.failure_step_index is None


async def test_assert_url_step_fails_on_mismatch(engine, fixture_site_url):
    steps = [
        _step(0, TestStepActionType.navigate, target_descriptor=fixture_site_url),
        _step(1, TestStepActionType.assert_url, expected_assertion="this-does-not-appear"),
    ]

    result, artifacts = await engine.run_test_case(_test_case(), steps, fixture_site_url)

    assert result.status == "failed"
    assert result.failure_step_index == 1
    assert result.error_message is not None
    assert len(artifacts) == 1
    assert artifacts[0].step_index == 1


async def test_assert_content_step_validates_visible_text(engine, fixture_site_url):
    steps = [
        _step(0, TestStepActionType.navigate, target_descriptor=f"{fixture_site_url}/about.html"),
        _step(1, TestStepActionType.assert_content, expected_assertion="This is the about page"),
    ]

    result, _artifacts = await engine.run_test_case(_test_case(), steps, fixture_site_url)

    assert result.status == "passed"


async def test_assert_element_step_validates_presence(engine, fixture_site_url):
    steps = [
        _step(0, TestStepActionType.navigate, target_descriptor=fixture_site_url),
        _step(1, TestStepActionType.assert_element, target_descriptor="#visible-box", expected_assertion="present"),
    ]

    result, _artifacts = await engine.run_test_case(_test_case(), steps, fixture_site_url)

    assert result.status == "passed"


async def test_assert_element_step_validates_absence(engine, fixture_site_url):
    steps = [
        _step(0, TestStepActionType.navigate, target_descriptor=fixture_site_url),
        _step(1, TestStepActionType.assert_element, target_descriptor="#hidden-box", expected_assertion="hidden"),
    ]

    result, _artifacts = await engine.run_test_case(_test_case(), steps, fixture_site_url)

    assert result.status == "passed"


async def test_assert_element_step_fails_when_element_missing(engine, fixture_site_url):
    steps = [
        _step(0, TestStepActionType.navigate, target_descriptor=fixture_site_url),
        _step(1, TestStepActionType.assert_element, target_descriptor="#does-not-exist", expected_assertion="present"),
    ]

    result, artifacts = await engine.run_test_case(_test_case(), steps, fixture_site_url)

    assert result.status == "failed"
    assert result.failure_step_index == 1
    assert len(artifacts) == 1


async def test_steps_execute_in_order_index_order_regardless_of_list_order(engine, fixture_site_url):
    steps = [
        _step(2, TestStepActionType.assert_content, expected_assertion="1"),
        _step(0, TestStepActionType.navigate, target_descriptor=fixture_site_url),
        _step(1, TestStepActionType.click, target_descriptor="#counter-btn"),
    ]

    result, _artifacts = await engine.run_test_case(_test_case(), steps, fixture_site_url)

    assert [entry.step_index for entry in result.execution_log] == [0, 1, 2]
    assert result.status == "passed"


async def test_step_flagged_for_checkpoint_screenshot_captures_one_even_on_success(engine, fixture_site_url):
    steps = [
        _step(0, TestStepActionType.navigate, target_descriptor=fixture_site_url, capture_screenshot=True),
    ]

    result, artifacts = await engine.run_test_case(_test_case(), steps, fixture_site_url)

    assert result.status == "passed"
    assert len(artifacts) == 1
    assert artifacts[0].content_type == "image/png"
    assert len(artifacts[0].data) > 0
