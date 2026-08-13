"""Playwright adapter (research.md #6, T126): a single pre-warmed `Browser`
per process, with a fresh `BrowserContext` created (and closed) for every
`load_page`/`run_test_case` call — never reused across calls (FR-067).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from urllib.parse import urlparse

from playwright.async_api import Browser, Page, Playwright, async_playwright

from testpilot.ai_provider.base import FormFieldSnapshot, FormSnapshot
from testpilot.execution.engine import (
    CapturedArtifact,
    LoadedPage,
    StepExecutionRecord,
    TestResult,
    TestResultStatus,
)
from testpilot.execution.steps import STEP_EXECUTORS, StepOutcome
from testpilot.projects.url_validation import Resolver, validate_public_url
from testpilot.testcases.models import TestCase, TestStep

_DEFAULT_TIMEOUT_MS = 15_000
_DEFAULT_STEP_TIMEOUT_MS = 10_000
_DEFAULT_TEST_CASE_TIMEOUT_MS = 120_000
_MAX_HEADINGS = 20
_MAX_LINKS = 30
_MAX_INTERACTIVE_ELEMENTS = 20

_HEADINGS_SCRIPT = f"(els) => els.slice(0, {_MAX_HEADINGS}).map(e => e.textContent.trim()).filter(Boolean)"
_INTERACTIVE_SCRIPT = (
    f"(els) => els.slice(0, {_MAX_INTERACTIVE_ELEMENTS}).map(e => e.textContent.trim()).filter(Boolean)"
)
_LINKS_SCRIPT = f"(els) => els.slice(0, {_MAX_LINKS}).map(e => e.href).filter(Boolean)"
_FORMS_SCRIPT = """(forms) => forms.map(f => ({
    action: f.getAttribute('action'),
    method: f.getAttribute('method'),
    fields: Array.from(f.querySelectorAll('input, textarea, select')).map(el => ({
        name: el.getAttribute('name') || el.getAttribute('id') || '',
        field_type: el.getAttribute('type') || el.tagName.toLowerCase(),
    })).filter(field => field.name)
}))"""


async def _extract_snapshot(page: Page) -> LoadedPage:
    title = await page.title()
    headings = await page.eval_on_selector_all("h1, h2, h3", _HEADINGS_SCRIPT)
    interactive_elements = await page.eval_on_selector_all("button, a[role=button]", _INTERACTIVE_SCRIPT)
    links = await page.eval_on_selector_all("a[href]", _LINKS_SCRIPT)

    forms_raw = await page.eval_on_selector_all("form", _FORMS_SCRIPT)
    forms = [
        FormSnapshot(
            action=form.get("action"),
            method=form.get("method"),
            fields=[
                FormFieldSnapshot(name=field["name"], field_type=field["field_type"])
                for field in form.get("fields", [])
            ],
        )
        for form in forms_raw
    ]

    return LoadedPage(
        url=page.url,
        title=title,
        headings=headings,
        forms=forms,
        interactive_elements=interactive_elements,
        links=list(dict.fromkeys(links)),
    )


class PlaywrightEngine:
    """Concrete `BrowserAutomationEngine` (execution/engine.py's Protocol:
    `load_page` and `run_test_case`)."""

    def __init__(
        self,
        *,
        timeout_ms: int = _DEFAULT_TIMEOUT_MS,
        step_timeout_ms: int = _DEFAULT_STEP_TIMEOUT_MS,
        test_case_timeout_ms: int = _DEFAULT_TEST_CASE_TIMEOUT_MS,
        url_resolver: Resolver | None = None,
    ) -> None:
        self._timeout_ms = timeout_ms
        self._step_timeout_ms = step_timeout_ms
        self._test_case_timeout_ms = test_case_timeout_ms
        # Threaded into validate_public_url's own injectable-resolver
        # mechanism (projects/url_validation.py, exercised the same way by
        # tests/unit/test_url_validation.py) — lets tests point the SSRF
        # guard's DNS step at a fake public address for a local fixture
        # server, without weakening the guard default production code uses.
        self._url_resolver = url_resolver
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def _check_url(self, url: str) -> None:
        if self._url_resolver is not None:
            await validate_public_url(url, resolver=self._url_resolver)
        else:
            await validate_public_url(url)

    async def _check_navigate_step_url(self, target_descriptor: str) -> None:
        """T207: `run_test_case`'s own SSRF check only covers the initial
        `target_url` navigate, once per run (documented, deliberate — see
        its own docstring) — but a `navigate` *step*'s `target_descriptor`
        is arbitrary, user-authored data (the UI itself labels it "URL or
        path", frontend/src/components/TestStepEditor.tsx), and
        `execute_navigate` (execution/steps.py) passes it straight to
        `page.goto()` with no validation of its own. A test case with a
        `navigate` step whose `target_descriptor` is an absolute URL
        (`http://169.254.169.254/...`) could otherwise navigate anywhere,
        bypassing the guard entirely (a genuine finding, not a
        pre-existing test). A *relative* path (`/checkout`) is safe by
        construction — Playwright resolves it against the current page,
        which is already anchored to an already-validated origin — so only
        absolute-URL targets are re-checked here.
        """
        if urlparse(target_descriptor).scheme:
            await self._check_url(target_descriptor)

    async def start(self) -> None:
        if self._browser is not None:
            return
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch()

    async def close(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def load_page(self, url: str) -> LoadedPage:
        # SSRF re-check immediately before navigation, at the engine
        # boundary itself (contracts/browser-automation-adapter.md
        # Isolation & safety contract) — mandatory even though callers
        # (ai_generation's site-analysis crawl) already validated the
        # project's URL at project-creation time.
        await self._check_url(url)

        await self.start()
        assert self._browser is not None

        context = await self._browser.new_context()
        try:
            page = await context.new_page()
            page.set_default_timeout(self._timeout_ms)
            await page.goto(url, wait_until="domcontentloaded")
            return await _extract_snapshot(page)
        finally:
            await context.close()

    async def run_test_case(
        self, test_case: TestCase, steps: list[TestStep], target_url: str
    ) -> tuple[TestResult, list[CapturedArtifact]]:
        """FR-059-FR-068: executes `steps` in `order_index` order against a
        fresh, isolated `BrowserContext` (FR-067), enforcing per-step and
        overall timeouts (FR-066), capturing a screenshot on failure (and on
        any step explicitly flagged for one, FR-064), and — per NFR-007/
        FR-075/T131 — never raising past this boundary: any unexpected
        engine-level failure (including the SSRF guard rejecting
        `target_url`, since a project's URL could have been edited between
        creation and this run) becomes a structured `status="error"`
        `TestResult` instead.
        """
        started_at = datetime.now(UTC)
        execution_log: list[StepExecutionRecord] = []
        artifacts: list[CapturedArtifact] = []

        try:
            # SSRF re-check immediately before the initial navigate of this
            # test case (contracts/browser-automation-adapter.md Isolation &
            # safety contract) — once per run, not once per navigate step.
            await self._check_url(target_url)

            await self.start()
            assert self._browser is not None

            context = await self._browser.new_context()
            try:
                page = await context.new_page()
                page.set_default_timeout(self._step_timeout_ms)

                async def _run_steps() -> tuple[TestResultStatus, int | None, str | None]:
                    status: TestResultStatus = "passed"
                    failure_step_index: int | None = None
                    error_message: str | None = None

                    for step in sorted(steps, key=lambda s: s.order_index):
                        executor = STEP_EXECUTORS.get(step.action_type)
                        try:
                            if executor is None:
                                outcome = StepOutcome(
                                    status="failed", message=f"Unsupported action_type {step.action_type!r}"
                                )
                            else:
                                if step.action_type == "navigate" and step.target_descriptor:
                                    await self._check_navigate_step_url(step.target_descriptor)
                                outcome = await asyncio.wait_for(
                                    executor(page, step), timeout=self._step_timeout_ms / 1000
                                )
                        except TimeoutError:
                            outcome = StepOutcome(
                                status="failed", message=f"Step timed out after {self._step_timeout_ms}ms"
                            )
                        except Exception as exc:  # noqa: BLE001 — a step's own failure, not an engine crash
                            outcome = StepOutcome(status="failed", message=str(exc))

                        execution_log.append(
                            StepExecutionRecord(
                                step_index=step.order_index,
                                action_type=str(step.action_type),
                                status=outcome.status,
                                message=outcome.message,
                                timestamp=datetime.now(UTC),
                            )
                        )

                        if step.capture_screenshot or outcome.status == "failed":
                            try:
                                screenshot = await page.screenshot()
                                artifacts.append(
                                    CapturedArtifact(
                                        step_index=step.order_index,
                                        content_type="image/png",
                                        data=screenshot,
                                        captured_at=datetime.now(UTC),
                                    )
                                )
                            except Exception:  # noqa: BLE001 — best-effort; must not mask the real outcome
                                pass

                        if outcome.status == "failed":
                            status = "failed"
                            failure_step_index = step.order_index
                            error_message = outcome.message
                            break

                    return status, failure_step_index, error_message

                try:
                    status, failure_step_index, error_message = await asyncio.wait_for(
                        _run_steps(), timeout=self._test_case_timeout_ms / 1000
                    )
                except TimeoutError:
                    status = "error"
                    failure_step_index = None
                    error_message = f"Test case exceeded its overall timeout of {self._test_case_timeout_ms}ms"

                completed_at = datetime.now(UTC)
                result = TestResult(
                    status=status,
                    execution_log=execution_log,
                    failure_step_index=failure_step_index,
                    error_message=error_message,
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_ms=int((completed_at - started_at).total_seconds() * 1000),
                )
                return result, artifacts
            finally:
                await context.close()
        except Exception as exc:  # noqa: BLE001 — T131: never raise past this boundary
            completed_at = datetime.now(UTC)
            result = TestResult(
                status="error",
                execution_log=execution_log,
                failure_step_index=None,
                error_message=str(exc),
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=int((completed_at - started_at).total_seconds() * 1000),
            )
            return result, artifacts
