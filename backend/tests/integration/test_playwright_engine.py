"""Integration test for the Playwright BrowserAutomationEngine adapter
(T126, prerequisite for Phase 9's T115 site-analysis step). Exercises a real
Chromium browser. Form-extraction is tested against a local static-file
fixture server (not a third-party site) so it isn't at the mercy of that
site's uptime; the "loads a real public page" and "rejects a private IP"
cases still use a real public domain / real DNS, the same class of
real-network dependency already accepted by the projects contract tests.
"""

import http.server
import threading
import uuid
from collections.abc import Iterator

import pytest

from testpilot.core.exceptions import UrlNotPublicError
from testpilot.execution.playwright_engine import PlaywrightEngine, _extract_snapshot
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

_FIXTURE_HTML = b"""<!doctype html>
<html>
<head><title>Fixture Page</title></head>
<body>
  <h1>Welcome</h1>
  <h2>Sign up</h2>
  <form action="/submit" method="post">
    <input name="email" type="email" />
    <input name="password" type="password" />
    <button type="submit">Create account</button>
  </form>
  <a href="/about">About</a>
</body>
</html>"""


class _FixtureHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(_FIXTURE_HTML)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


@pytest.fixture(scope="module")
def fixture_server_port() -> Iterator[int]:
    server = http.server.HTTPServer(("127.0.0.1", 0), _FixtureHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield port
    server.shutdown()
    thread.join(timeout=5)


@pytest.fixture
async def engine():
    eng = PlaywrightEngine()
    yield eng
    await eng.close()


async def test_load_page_extracts_title_and_headings(engine):
    page = await engine.load_page("https://example.com")

    assert page.url.startswith("https://example.com")
    assert page.title != ""


async def test_load_page_rejects_a_private_ip_url(engine):
    with pytest.raises(UrlNotPublicError):
        await engine.load_page("http://127.0.0.1/")


async def test_extract_snapshot_reads_headings_forms_and_links(engine, fixture_server_port):
    """Exercises the same extraction logic load_page uses, against a local
    fixture — bypassing load_page's own SSRF guard (which correctly rejects
    127.0.0.1, verified separately above) since this test is about
    extraction correctness, not the guard itself."""
    await engine.start()
    assert engine._browser is not None  # noqa: SLF001
    context = await engine._browser.new_context()  # noqa: SLF001
    try:
        page = await context.new_page()
        await page.goto(f"http://127.0.0.1:{fixture_server_port}/", wait_until="domcontentloaded")
        snapshot = await _extract_snapshot(page)
    finally:
        await context.close()

    assert snapshot.title == "Fixture Page"
    assert "Welcome" in snapshot.headings
    assert "Sign up" in snapshot.headings
    assert len(snapshot.forms) == 1
    form = snapshot.forms[0]
    assert form.action == "/submit"
    assert form.method == "post"
    assert {field.name for field in form.fields} == {"email", "password"}
    assert "Create account" in snapshot.interactive_elements
    assert any(link.endswith("/about") for link in snapshot.links)


async def test_extract_snapshot_dedupes_links(engine, fixture_server_port):
    await engine.start()
    assert engine._browser is not None  # noqa: SLF001
    context = await engine._browser.new_context()  # noqa: SLF001
    try:
        page = await context.new_page()
        await page.goto(f"http://127.0.0.1:{fixture_server_port}/", wait_until="domcontentloaded")
        snapshot = await _extract_snapshot(page)
    finally:
        await context.close()

    assert len(snapshot.links) == len(set(snapshot.links))


def _in_memory_test_case_and_steps(*, first_navigate_target: str, second_navigate_target: str) -> tuple[TestCase, list[TestStep]]:
    """Never persisted — run_test_case only ever reads these fields, so a
    plain in-memory instance (fake but well-formed IDs) is enough. Step 0
    must itself be a `navigate` (run_test_case starts every case on a blank
    page, matching every other test case fixture across this suite) so
    step 1's `navigate` has an established origin to be relative to."""
    organization_id = uuid.uuid4()
    project_id = uuid.uuid4()
    test_case_id = uuid.uuid4()
    test_case = TestCase(
        id=test_case_id,
        organization_id=organization_id,
        project_id=project_id,
        title="SSRF bypass probe",
        description="d",
        priority=TestCasePriority.medium,
        severity=TestCaseSeverity.major,
        status=TestCaseStatus.approved,
        source=TestCaseSource.manual,
    )
    steps = [
        TestStep(
            organization_id=organization_id,
            test_case_id=test_case_id,
            order_index=0,
            action_type=TestStepActionType.navigate,
            target_descriptor=first_navigate_target,
        ),
        TestStep(
            organization_id=organization_id,
            test_case_id=test_case_id,
            order_index=1,
            action_type=TestStepActionType.navigate,
            target_descriptor=second_navigate_target,
        ),
    ]
    return test_case, steps


async def test_run_test_case_rejects_an_absolute_url_navigate_step_targeting_a_private_address(engine):
    """T207: the SSRF guard's own docstring says it's re-checked "once per
    run, not once per navigate step" for the *initial* target_url — but a
    `navigate` step's own `target_descriptor` is separate, arbitrary,
    user-authored data (frontend labels it "URL or path") that
    execute_navigate previously passed straight to page.goto() with no
    validation at all. A test case whose second step targets a private
    address absolutely (not relative to the already-validated origin) must
    have that step fail, not silently navigate there."""
    test_case, steps = _in_memory_test_case_and_steps(
        first_navigate_target="https://example.com", second_navigate_target="http://127.0.0.1/"
    )

    result, _artifacts = await engine.run_test_case(test_case, steps, "https://example.com")

    assert result.status == "failed"
    navigate_log = next(entry for entry in result.execution_log if entry.step_index == 1)
    assert navigate_log.status == "failed"
    assert "non-public" in (navigate_log.message or "") or "not a valid" in (navigate_log.message or "")


async def test_run_test_case_does_not_ssrf_reject_a_relative_navigate_step(fixture_server_port):
    """A relative target_descriptor must NOT be rejected by the SSRF
    re-check specifically -- it has no scheme/hostname of its own to
    validate, so `_check_navigate_step_url` must skip it entirely and let
    Playwright's own `page.goto()` handle (or itself reject) it.

    This does NOT assert the step *passes* end-to-end: `page.goto()`
    requires a fully-qualified URL and has no notion of "relative to the
    current page" the way a clicked in-page link would (a real, separate,
    pre-existing limitation of `execute_navigate` unrelated to SSRF and out
    of T207's scope) -- only that whatever failure occurs is Playwright's
    own protocol error, not this task's SSRF guard.
    """

    async def _public_resolver(hostname: str) -> list[str]:
        return ["8.8.8.8"]

    fixture_url = f"http://127.0.0.1:{fixture_server_port}/"
    test_case, steps = _in_memory_test_case_and_steps(
        first_navigate_target=fixture_url, second_navigate_target="/about"
    )
    engine = PlaywrightEngine(url_resolver=_public_resolver)
    try:
        result, _artifacts = await engine.run_test_case(test_case, steps, fixture_url)
    finally:
        await engine.close()

    navigate_log = next(entry for entry in result.execution_log if entry.step_index == 1)
    message = navigate_log.message or ""
    assert "non-public" not in message
    assert "not a valid" not in message
