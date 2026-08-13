"""Fault-injection test: context crash and missing-element cases return a
structured error result rather than raising (T124,
contracts/browser-automation-adapter.md Isolation & safety contract,
NFR-007/FR-075/T131), plus dedicated coverage for the per-step/overall
timeout enforcement (T129) and the SSRF re-check (T130) that T123's
happy-path fixture-site tests don't otherwise exercise.

Uses the local fixture site (tests/fixtures/fixture_site/) served by
tests/fixtures/server.py, not a third-party site.
"""

import uuid

import pytest

from testpilot.core.exceptions import UrlNotPublicError
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
        title="Fault-injection walkthrough",
        description="Exercises crash, timeout, and SSRF fault paths.",
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
    # Same fixture-site-vs-SSRF-guard workaround as test_browser_engine.py:
    # the fixture server is on 127.0.0.1, which the real resolver correctly
    # rejects. Injected only in tests via PlaywrightEngine's resolver hook.
    return ["8.8.8.8"]


@pytest.fixture
async def engine():
    eng = PlaywrightEngine(url_resolver=_public_resolver)
    yield eng
    await eng.close()


async def test_browser_crash_returns_a_structured_error_result_instead_of_raising(
    engine, fixture_site_url
):
    """T131: if the underlying browser connection dies mid-run (simulated
    here by closing the Playwright Browser out from under the engine before
    it opens a new context), run_test_case must return status="error"
    rather than letting the PlaywrightError propagate."""
    await engine.start()
    assert engine._browser is not None  # noqa: SLF001
    await engine._browser.close()  # noqa: SLF001 — simulates a crashed/disconnected browser

    steps = [_step(0, TestStepActionType.navigate, target_descriptor=fixture_site_url)]

    result, artifacts = await engine.run_test_case(_test_case(), steps, fixture_site_url)

    assert result.status == "error"
    assert result.error_message is not None
    assert artifacts == []


async def test_click_on_a_missing_element_returns_a_failed_result_not_an_exception(
    engine, fixture_site_url
):
    """A missing element is a normal test failure, not an engine crash —
    status="failed" with a populated failure_step_index, never a raised
    exception past the engine boundary."""
    steps = [
        _step(0, TestStepActionType.navigate, target_descriptor=fixture_site_url),
        _step(1, TestStepActionType.click, target_descriptor="#this-element-does-not-exist"),
    ]

    result, artifacts = await engine.run_test_case(_test_case(), steps, fixture_site_url)

    assert result.status == "failed"
    assert result.failure_step_index == 1
    assert result.error_message is not None
    assert len(artifacts) == 1  # screenshot captured on failure (FR-064)


async def test_unsupported_action_type_returns_a_failed_result_not_an_exception(
    engine, fixture_site_url
):
    """A step referencing an action_type with no registered executor must
    fail gracefully rather than raise a KeyError."""
    steps = [
        _step(0, TestStepActionType.navigate, target_descriptor=fixture_site_url),
        _step(1, "not_a_real_action_type", target_descriptor="#visible-box"),  # type: ignore[arg-type]
    ]

    result, artifacts = await engine.run_test_case(_test_case(), steps, fixture_site_url)

    assert result.status == "failed"
    assert result.failure_step_index == 1


async def test_per_step_timeout_fails_the_step_without_hanging(fixture_site_url):
    """T129: a step that can't complete within the per-step timeout budget
    must produce a failed step (status="failed" for the run overall, since
    it's the only step) rather than hanging indefinitely."""
    engine = PlaywrightEngine(url_resolver=_public_resolver, step_timeout_ms=1)
    try:
        steps = [_step(0, TestStepActionType.navigate, target_descriptor=fixture_site_url)]

        result, _artifacts = await engine.run_test_case(_test_case(), steps, fixture_site_url)

        assert result.status == "failed"
        assert result.execution_log[0].status == "failed"
        assert "timed out" in (result.execution_log[0].message or "")
    finally:
        await engine.close()


async def test_overall_test_case_timeout_returns_an_error_result(fixture_site_url):
    """T129: if the whole test case can't complete within its overall
    timeout budget (even though each individual step might complete within
    its own per-step budget), the engine must return status="error" rather
    than hang past the caller's deadline."""
    engine = PlaywrightEngine(
        url_resolver=_public_resolver, step_timeout_ms=10_000, test_case_timeout_ms=1
    )
    try:
        steps = [_step(0, TestStepActionType.navigate, target_descriptor=fixture_site_url)]

        result, _artifacts = await engine.run_test_case(_test_case(), steps, fixture_site_url)

        assert result.status == "error"
        assert result.error_message is not None
        assert "timeout" in result.error_message.lower()
    finally:
        await engine.close()


async def test_ssrf_guard_rejects_a_non_public_target_url_as_a_structured_error():
    """T130: the SSRF re-check runs with the engine's real (non-injected)
    resolver by default — a target_url that resolves to a loopback address
    must be rejected, but as a structured status="error" TestResult (per
    plan.md's "a project's URL could be edited between creation and
    execution" scenario), never a raised UrlNotPublicError."""
    engine = PlaywrightEngine()
    try:
        steps = [_step(0, TestStepActionType.navigate, target_descriptor="http://127.0.0.1/")]

        result, artifacts = await engine.run_test_case(
            _test_case(), steps, "http://127.0.0.1/"
        )

        assert result.status == "error"
        assert result.error_message is not None
        assert result.execution_log == []
        assert artifacts == []
    finally:
        await engine.close()


async def test_load_page_still_raises_directly_on_ssrf_rejection():
    """Confirms run_test_case's never-raise behavior is a deliberate
    divergence from load_page (Phase 9), not an accidental inconsistency —
    load_page still raises UrlNotPublicError directly, since it has no
    TestResult shape to report a structured failure through."""
    engine = PlaywrightEngine()
    try:
        with pytest.raises(UrlNotPublicError):
            await engine.load_page("http://127.0.0.1/")
    finally:
        await engine.close()
