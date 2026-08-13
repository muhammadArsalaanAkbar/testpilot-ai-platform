"""Step-executor primitives (T127/T128, contracts/browser-automation-adapter.md,
FR-059-FR-063) — one function per `TestStepActionType`. Adding a new
action_type means adding one new function and a `STEP_EXECUTORS` entry, not
changing `run_test_case`'s signature or the `TestResult` shape (FR-068).

Locator resolution (`_locate`): tries `target_descriptor` as a CSS selector
first (works for the fixture site's explicit ids/classes, and for any
well-formed AI-generated selector); falls back to matching visible text if
no CSS match is found, since AI-generated `target_descriptor` values aren't
guaranteed to be strict selectors (e.g. a button's visible label).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Locator, Page

from testpilot.testcases.models import TestStep

StepOutcomeStatus = Literal["passed", "failed"]


@dataclass(frozen=True)
class StepOutcome:
    status: StepOutcomeStatus
    message: str | None = None


async def _locator_count(locator: Locator) -> int:
    try:
        return await locator.count()
    except PlaywrightError:
        return 0


async def _locate(page: Page, descriptor: str) -> Locator:
    css_locator = page.locator(descriptor)
    if await _locator_count(css_locator) > 0:
        return css_locator.first
    return page.get_by_text(descriptor, exact=False).first


async def execute_navigate(page: Page, step: TestStep) -> StepOutcome:
    """FR-059: open the target website and navigate between pages."""
    target = step.target_descriptor
    if not target:
        return StepOutcome(status="failed", message="navigate step has no target_descriptor")
    await page.goto(target, wait_until="domcontentloaded")
    return StepOutcome(status="passed")


async def execute_click(page: Page, step: TestStep) -> StepOutcome:
    """FR-060: click elements."""
    if not step.target_descriptor:
        return StepOutcome(status="failed", message="click step has no target_descriptor")
    locator = await _locate(page, step.target_descriptor)
    if await _locator_count(locator) == 0:
        return StepOutcome(status="failed", message=f"No element found matching {step.target_descriptor!r}")
    await locator.click()
    return StepOutcome(status="passed")


async def execute_type(page: Page, step: TestStep) -> StepOutcome:
    """FR-060: enter text into fields."""
    if not step.target_descriptor:
        return StepOutcome(status="failed", message="type step has no target_descriptor")
    locator = await _locate(page, step.target_descriptor)
    if await _locator_count(locator) == 0:
        return StepOutcome(status="failed", message=f"No element found matching {step.target_descriptor!r}")
    await locator.fill(step.input_value or "")
    return StepOutcome(status="passed")


async def execute_submit(page: Page, step: TestStep) -> StepOutcome:
    """FR-060: submit forms. Simulates a real user interaction (clicking the
    submit control) rather than calling the DOM's `.submit()` directly —
    `target_descriptor` may describe the form or its submit button; falls
    back to any submit control on the page if it doesn't resolve to one."""
    descriptor = step.target_descriptor
    if descriptor:
        locator = await _locate(page, descriptor)
        if await _locator_count(locator) > 0:
            await locator.click()
            return StepOutcome(status="passed")

    fallback = page.locator("button[type=submit], input[type=submit]").first
    if await _locator_count(fallback) == 0:
        return StepOutcome(status="failed", message="No submit control found on the page")
    await fallback.click()
    return StepOutcome(status="passed")


async def execute_assert_url(page: Page, step: TestStep) -> StepOutcome:
    """FR-061: validate the resulting page URL against an expected value."""
    expected = step.expected_assertion or ""
    current = page.url
    if expected and expected in current:
        return StepOutcome(status="passed")
    return StepOutcome(status="failed", message=f"Expected URL to contain {expected!r}, got {current!r}")


async def execute_assert_content(page: Page, step: TestStep) -> StepOutcome:
    """FR-062: validate page content (visible text) against an expected value."""
    expected = step.expected_assertion or ""
    if not expected:
        return StepOutcome(status="failed", message="assert_content step has no expected_assertion")
    locator = page.get_by_text(expected, exact=False)
    if await _locator_count(locator) > 0:
        return StepOutcome(status="passed")
    return StepOutcome(status="failed", message=f"Expected page content to contain {expected!r}")


async def execute_assert_element(page: Page, step: TestStep) -> StepOutcome:
    """FR-063: validate presence, absence, or state of a UI element.
    `expected_assertion` is one of `present` (default), `absent`, `visible`,
    `hidden`."""
    if not step.target_descriptor:
        return StepOutcome(status="failed", message="assert_element step has no target_descriptor")

    expectation = (step.expected_assertion or "present").strip().lower()
    locator = page.locator(step.target_descriptor)
    count = await _locator_count(locator)

    if expectation in ("absent", "not present"):
        if count == 0:
            return StepOutcome(status="passed")
        return StepOutcome(status="failed", message=f"Expected element {step.target_descriptor!r} to be absent")

    if expectation == "hidden":
        if count == 0:
            return StepOutcome(status="passed")
        if not await locator.first.is_visible():
            return StepOutcome(status="passed")
        return StepOutcome(status="failed", message=f"Expected element {step.target_descriptor!r} to be hidden")

    # "present" / "visible" (default)
    if count == 0:
        return StepOutcome(status="failed", message=f"Expected element {step.target_descriptor!r} to be present")
    if expectation == "visible" and not await locator.first.is_visible():
        return StepOutcome(status="failed", message=f"Expected element {step.target_descriptor!r} to be visible")
    return StepOutcome(status="passed")


STEP_EXECUTORS: dict[str, Callable[[Page, TestStep], Awaitable[StepOutcome]]] = {
    "navigate": execute_navigate,
    "click": execute_click,
    "type": execute_type,
    "submit": execute_submit,
    "assert_url": execute_assert_url,
    "assert_content": execute_assert_content,
    "assert_element": execute_assert_element,
}
