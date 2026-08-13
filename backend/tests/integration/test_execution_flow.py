"""Integration test: real, non-mocked Playwright execution through the
runner orchestrator (T135, FR-070/FR-074/FR-075, plus the reliability
checks called out for Phase 11: state transitions, persistence after both
successful and failed execution, fault isolation not leaving a run stuck in
"running", timeout handling, retry-failed scoping, and RLS isolation).

Directly invokes `execution.runner.run_test_run` — the exact function the
real `rq worker` process calls via `worker/jobs/execute_test_run.py`'s
`handle` — rather than running a live worker, matching
test_ai_generation_flow.py's precedent for testing orchestration
correctness independent of queue transport (already covered by
test_test_runs.py's contract tests).

Uses the REAL `PlaywrightEngine` (Phase 10, unmodified) driving a real
Chromium browser against the local fixture site (tests/fixtures/fixture_site/)
— never a fake/mocked engine, per this phase's explicit "no mocked success
responses for the actual execution flow" requirement. A project's URL is
created against a real public domain (so project-creation's own SSRF check
passes normally), then updated directly in the DB to point at the local
fixture server before execution — this is not a test shortcut, it is
deliberately the exact "a project's URL could be edited between creation and
execution" scenario plan.md's own commentary uses to justify run_test_case's
own execution-time SSRF re-check (Phase 10, T130); the engine's injectable
`url_resolver` (also Phase 10) is used only to make that re-check treat the
loopback fixture address as public, exactly as tests/contract/test_browser_engine.py
already does for the engine in isolation.
"""

import uuid

import pytest
from sqlalchemy import select

from testpilot.core import cache
from testpilot.core.db import session_scope
from testpilot.execution import runner
from testpilot.execution.models import TestResult, TestRun, TestRunStatus
from testpilot.execution.playwright_engine import PlaywrightEngine
from testpilot.orgs.models import Organization, SubscriptionPlan
from testpilot.projects.models import Project
from testpilot.testcases.models import TestCase, TestStep

pytestmark = pytest.mark.anyio


async def _public_resolver(hostname: str) -> list[str]:
    return ["8.8.8.8"]


async def _signup_and_get_token(client, email="exec-flow@example.com"):
    r = await client.post(
        "/auth/signup", json={"email": email, "password": "correct horse battery staple", "name": "Exec Flow"}
    )
    body = r.json()
    return body["access_token"], body["organization"]["id"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_project(client, token, name="Exec Flow Project"):
    r = await client.post("/projects", json={"name": name, "url": "https://example.com"}, headers=_auth_headers(token))
    return r.json()["id"]


async def _point_project_at_fixture_site(*, organization_id: uuid.UUID, project_id: uuid.UUID, fixture_site_url: str) -> None:
    """Simulates the project's URL being edited after creation (see module
    docstring) — bypasses the HTTP layer's own SSRF-at-creation check
    deliberately, the same way Phase 10's tests bypass load_page's guard to
    exercise extraction logic against a local fixture."""
    async with session_scope(organization_id=str(organization_id)) as session:
        result = await session.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one()
        project.url = fixture_site_url
        session.add(project)


async def _create_approved_test_case(client, token, project_id, *, title, steps):
    create = await client.post(
        f"/projects/{project_id}/test-cases",
        json={"title": title, "description": "D", "priority": "low", "severity": "minor", "steps": steps},
        headers=_auth_headers(token),
    )
    test_case_id = create.json()["id"]
    await client.post(f"/projects/{project_id}/test-cases/{test_case_id}/approve", headers=_auth_headers(token))
    return test_case_id


_PASSING_STEPS_A = [
    {"action_type": "navigate", "target_descriptor": "/"},
    {"action_type": "assert_content", "expected_assertion": "Fixture Home"},
]
_PASSING_STEPS_B = [
    {"action_type": "navigate", "target_descriptor": "/"},
    {"action_type": "click", "target_descriptor": "#counter-btn"},
    {"action_type": "assert_content", "expected_assertion": "1"},
]
_FAILING_STEPS = [
    {"action_type": "navigate", "target_descriptor": "/"},
    {"action_type": "assert_element", "target_descriptor": "#does-not-exist", "expected_assertion": "present"},
]


def _relative_to_absolute(steps: list[dict], base_url: str) -> list[dict]:
    return [
        {**step, "target_descriptor": base_url + step["target_descriptor"]}
        if step["action_type"] == "navigate"
        else step
        for step in steps
    ]


async def test_run_of_three_cases_two_pass_one_fail_produces_correct_summary_counters(client, fixture_site_url):
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    case_a = await _create_approved_test_case(
        client, token, project_id, title="Pass A", steps=_relative_to_absolute(_PASSING_STEPS_A, fixture_site_url)
    )
    case_b = await _create_approved_test_case(
        client, token, project_id, title="Pass B", steps=_relative_to_absolute(_PASSING_STEPS_B, fixture_site_url)
    )
    case_c = await _create_approved_test_case(
        client, token, project_id, title="Fail C", steps=_relative_to_absolute(_FAILING_STEPS, fixture_site_url)
    )

    await _point_project_at_fixture_site(
        organization_id=uuid.UUID(organization_id), project_id=uuid.UUID(project_id), fixture_site_url=fixture_site_url
    )

    create = await client.post(
        f"/projects/{project_id}/test-runs",
        json={"test_case_ids": [case_a, case_b, case_c]},
        headers=_auth_headers(token),
    )
    assert create.status_code == 202
    run_id = create.json()["id"]

    engine = PlaywrightEngine(url_resolver=_public_resolver)
    try:
        await runner.run_test_run(test_run_id=uuid.UUID(run_id), organization_id=uuid.UUID(organization_id), engine=engine)
    finally:
        await engine.close()

    status_response = await client.get(f"/projects/{project_id}/test-runs/{run_id}", headers=_auth_headers(token))
    assert status_response.status_code == 200
    body = status_response.json()
    run_body = body["test_run"]

    assert run_body["status"] == "completed"
    assert run_body["summary_total"] == 3
    assert run_body["summary_passed"] == 2
    assert run_body["summary_failed"] == 1
    assert run_body["summary_skipped"] == 0
    assert run_body["started_at"] is not None
    assert run_body["completed_at"] is not None
    assert run_body["completed_at"] >= run_body["started_at"]

    results_by_case = {r["test_case_id"]: r for r in body["results"]}
    assert results_by_case[case_a]["status"] == "passed"
    assert results_by_case[case_b]["status"] == "passed"
    assert results_by_case[case_c]["status"] == "failed"
    assert results_by_case[case_c]["failure_step_index"] == 1
    assert results_by_case[case_c]["error_message"]
    for result in body["results"]:
        assert result["duration_ms"] >= 0

    # FR-056: last_result on each test case reflects its most recent outcome.
    case_a_detail = await client.get(f"/projects/{project_id}/test-cases/{case_a}", headers=_auth_headers(token))
    assert case_a_detail.json()["test_case"]["last_result"] == "passed"
    case_c_detail = await client.get(f"/projects/{project_id}/test-cases/{case_c}", headers=_auth_headers(token))
    assert case_c_detail.json()["test_case"]["last_result"] == "failed"


async def test_engine_captures_a_screenshot_artifact_for_the_failing_case(client, fixture_site_url):
    """FR-064: a failed step must produce a captured screenshot. Durable
    storage for it (S3/MinIO, the `artifacts` table) is Phase 12 — this
    verifies the plumbing genuinely reaches the runner's engine call with a
    non-empty artifact, rather than silently dropping it, which is the part
    of FR-064 actually within Phase 11's scope."""
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    case_c = await _create_approved_test_case(
        client, token, project_id, title="Fail C", steps=_relative_to_absolute(_FAILING_STEPS, fixture_site_url)
    )
    await _point_project_at_fixture_site(
        organization_id=uuid.UUID(organization_id), project_id=uuid.UUID(project_id), fixture_site_url=fixture_site_url
    )

    engine = PlaywrightEngine(url_resolver=_public_resolver)
    try:
        async with session_scope(organization_id=organization_id) as session:
            case_result = await session.execute(select(TestCase).where(TestCase.id == uuid.UUID(case_c)))
            test_case = case_result.scalar_one()
            steps_result = await session.execute(
                select(TestStep).where(TestStep.test_case_id == test_case.id).order_by(TestStep.order_index)
            )
            steps = list(steps_result.scalars().all())

        engine_result, artifacts = await engine.run_test_case(test_case, steps, fixture_site_url)
    finally:
        await engine.close()

    assert engine_result.status == "failed"
    assert len(artifacts) == 1
    assert artifacts[0].content_type == "image/png"
    assert len(artifacts[0].data) > 0


async def test_a_crashing_case_is_isolated_and_the_run_still_completes(client, fixture_site_url):
    """FR-075/NFR-007: one test case's engine-level crash must not abort the
    run — it is recorded as that case's own error result, and the run still
    reaches a completed terminal state (not stuck in "running", and not the
    run-level "error" status, which is reserved for an orchestration-level
    failure — see the next test)."""
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    good_case = await _create_approved_test_case(
        client, token, project_id, title="Good", steps=_relative_to_absolute(_PASSING_STEPS_A, fixture_site_url)
    )
    crashing_case = await _create_approved_test_case(
        client, token, project_id, title="Crashing", steps=_relative_to_absolute(_PASSING_STEPS_A, fixture_site_url)
    )
    await _point_project_at_fixture_site(
        organization_id=uuid.UUID(organization_id), project_id=uuid.UUID(project_id), fixture_site_url=fixture_site_url
    )

    create = await client.post(
        f"/projects/{project_id}/test-runs",
        json={"test_case_ids": [good_case, crashing_case]},
        headers=_auth_headers(token),
    )
    run_id = create.json()["id"]

    class _CrashingWrapperEngine:
        """Wraps the real engine but raises for one specific case, simulating
        an unexpected engine-level exception escaping run_test_case's own
        fault isolation (e.g. a Playwright process-level failure)."""

        def __init__(self, real_engine, crash_for_case_id):
            self._real = real_engine
            self._crash_for = crash_for_case_id

        async def run_test_case(self, test_case, steps, target_url):
            if str(test_case.id) == self._crash_for:
                raise RuntimeError("simulated browser process crash")
            return await self._real.run_test_case(test_case, steps, target_url)

        async def load_page(self, url):
            return await self._real.load_page(url)

    real_engine = PlaywrightEngine(url_resolver=_public_resolver)
    engine = _CrashingWrapperEngine(real_engine, crashing_case)
    try:
        await runner.run_test_run(test_run_id=uuid.UUID(run_id), organization_id=uuid.UUID(organization_id), engine=engine)
    finally:
        await real_engine.close()

    status_response = await client.get(f"/projects/{project_id}/test-runs/{run_id}", headers=_auth_headers(token))
    run_body = status_response.json()["test_run"]
    results_by_case = {r["test_case_id"]: r for r in status_response.json()["results"]}

    assert run_body["status"] == "completed"
    assert run_body["summary_passed"] == 1
    assert run_body["summary_failed"] == 1
    assert results_by_case[good_case]["status"] == "passed"
    assert results_by_case[crashing_case]["status"] == "error"
    assert "simulated browser process crash" in results_by_case[crashing_case]["error_message"]


async def test_an_orchestration_level_failure_still_reaches_a_terminal_state(client, fixture_site_url, monkeypatch):
    """A failure `_execute_one_case`'s own per-case isolation cannot catch —
    because it happens outside that function entirely, e.g. persisting the
    run's own final status transition — must still land the run in a
    terminal status rather than leaving it stuck in "running" forever.

    Genuine DB-level corruption can't deterministically trigger this: every
    row this orchestration touches is FK-protected (deleting the project
    CASCADEs and takes the run with it, rather than leaving a dangling
    reference — the correct, intended behavior, just not one that produces
    this failure mode). So the collaborator that would fail in a real
    "DB blipped mid-run" scenario is monkeypatched to raise once, which
    still exercises run_test_run's own real outer try/except — the thing
    actually under test — rather than faking the run's outcome."""
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    case_id = await _create_approved_test_case(
        client, token, project_id, title="Case", steps=_relative_to_absolute(_PASSING_STEPS_A, fixture_site_url)
    )
    await _point_project_at_fixture_site(
        organization_id=uuid.UUID(organization_id), project_id=uuid.UUID(project_id), fixture_site_url=fixture_site_url
    )
    create = await client.post(
        f"/projects/{project_id}/test-runs", json={"test_case_ids": [case_id]}, headers=_auth_headers(token)
    )
    run_id = create.json()["id"]

    real_persist_result = runner._persist_result

    async def _persist_result_that_fails_once(**kwargs):
        raise RuntimeError("simulated DB failure while persisting a case result")

    monkeypatch.setattr(runner, "_persist_result", _persist_result_that_fails_once)

    engine = PlaywrightEngine(url_resolver=_public_resolver)
    try:
        await runner.run_test_run(test_run_id=uuid.UUID(run_id), organization_id=uuid.UUID(organization_id), engine=engine)
    finally:
        await engine.close()
        monkeypatch.setattr(runner, "_persist_result", real_persist_result)

    async with session_scope(organization_id=organization_id) as session:
        result = await session.execute(select(TestRun).where(TestRun.id == uuid.UUID(run_id)))
        run = result.scalar_one()
        assert run.status == TestRunStatus.error
        assert run.completed_at is not None


async def test_per_step_timeout_fails_only_that_case_without_hanging_the_run(client, fixture_site_url):
    """T129 exercised inside the full orchestration: a case whose step can't
    complete within its timeout budget must fail cleanly, and the run must
    still reach a completed state promptly (not hang)."""
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    case_id = await _create_approved_test_case(
        client, token, project_id, title="Slow", steps=_relative_to_absolute(_PASSING_STEPS_A, fixture_site_url)
    )
    await _point_project_at_fixture_site(
        organization_id=uuid.UUID(organization_id), project_id=uuid.UUID(project_id), fixture_site_url=fixture_site_url
    )
    create = await client.post(
        f"/projects/{project_id}/test-runs", json={"test_case_ids": [case_id]}, headers=_auth_headers(token)
    )
    run_id = create.json()["id"]

    engine = PlaywrightEngine(url_resolver=_public_resolver, step_timeout_ms=1)
    try:
        await runner.run_test_run(test_run_id=uuid.UUID(run_id), organization_id=uuid.UUID(organization_id), engine=engine)
    finally:
        await engine.close()

    status_response = await client.get(f"/projects/{project_id}/test-runs/{run_id}", headers=_auth_headers(token))
    body = status_response.json()
    assert body["test_run"]["status"] == "completed"
    assert body["results"][0]["status"] == "failed"
    assert "timed out" in body["results"][0]["error_message"]


async def test_retry_failed_creates_a_new_run_scoped_to_only_the_failed_cases(client, fixture_site_url):
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    passing_case = await _create_approved_test_case(
        client, token, project_id, title="Pass", steps=_relative_to_absolute(_PASSING_STEPS_A, fixture_site_url)
    )
    failing_case = await _create_approved_test_case(
        client, token, project_id, title="Fail", steps=_relative_to_absolute(_FAILING_STEPS, fixture_site_url)
    )
    await _point_project_at_fixture_site(
        organization_id=uuid.UUID(organization_id), project_id=uuid.UUID(project_id), fixture_site_url=fixture_site_url
    )

    create = await client.post(
        f"/projects/{project_id}/test-runs",
        json={"test_case_ids": [passing_case, failing_case]},
        headers=_auth_headers(token),
    )
    first_run_id = create.json()["id"]

    engine = PlaywrightEngine(url_resolver=_public_resolver)
    try:
        await runner.run_test_run(
            test_run_id=uuid.UUID(first_run_id), organization_id=uuid.UUID(organization_id), engine=engine
        )

        retry = await client.post(
            f"/projects/{project_id}/test-runs/{first_run_id}/retry-failed", headers=_auth_headers(token)
        )
        assert retry.status_code == 202
        second_run_id = retry.json()["id"]
        assert retry.json()["summary_total"] == 1

        await runner.run_test_run(
            test_run_id=uuid.UUID(second_run_id), organization_id=uuid.UUID(organization_id), engine=engine
        )
    finally:
        await engine.close()

    second_run = await client.get(f"/projects/{project_id}/test-runs/{second_run_id}", headers=_auth_headers(token))
    second_body = second_run.json()
    assert len(second_body["results"]) == 1
    assert second_body["results"][0]["test_case_id"] == failing_case

    # The original run's own results are untouched by the retry.
    first_run = await client.get(f"/projects/{project_id}/test-runs/{first_run_id}", headers=_auth_headers(token))
    assert len(first_run.json()["results"]) == 2


async def test_test_case_with_no_steps_is_skipped_not_falsely_passed(client, fixture_site_url):
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    empty_case = await _create_approved_test_case(client, token, project_id, title="Empty", steps=[])
    await _point_project_at_fixture_site(
        organization_id=uuid.UUID(organization_id), project_id=uuid.UUID(project_id), fixture_site_url=fixture_site_url
    )
    create = await client.post(
        f"/projects/{project_id}/test-runs", json={"test_case_ids": [empty_case]}, headers=_auth_headers(token)
    )
    run_id = create.json()["id"]

    engine = PlaywrightEngine(url_resolver=_public_resolver)
    try:
        await runner.run_test_run(test_run_id=uuid.UUID(run_id), organization_id=uuid.UUID(organization_id), engine=engine)
    finally:
        await engine.close()

    status_response = await client.get(f"/projects/{project_id}/test-runs/{run_id}", headers=_auth_headers(token))
    body = status_response.json()
    assert body["test_run"]["summary_skipped"] == 1
    assert body["results"][0]["status"] == "skipped"


async def test_cross_tenant_test_results_are_invisible_under_rls(client, fixture_site_url):
    """A genuine DB-level RLS check (distinct from test_test_runs.py's
    black-box HTTP 404 check): rows genuinely exist for Organization A, but
    a session scoped to Organization B's RLS context must see zero of them
    even when querying test_results directly."""
    token_a, organization_id_a = await _signup_and_get_token(client, email="rls-a@example.com")
    project_id_a = await _create_project(client, token_a)
    case_a = await _create_approved_test_case(
        client, token_a, project_id_a, title="A", steps=_relative_to_absolute(_PASSING_STEPS_A, fixture_site_url)
    )
    await _point_project_at_fixture_site(
        organization_id=uuid.UUID(organization_id_a), project_id=uuid.UUID(project_id_a), fixture_site_url=fixture_site_url
    )
    create = await client.post(
        f"/projects/{project_id_a}/test-runs", json={"test_case_ids": [case_a]}, headers=_auth_headers(token_a)
    )
    run_id_a = create.json()["id"]

    engine = PlaywrightEngine(url_resolver=_public_resolver)
    try:
        await runner.run_test_run(
            test_run_id=uuid.UUID(run_id_a), organization_id=uuid.UUID(organization_id_a), engine=engine
        )
    finally:
        await engine.close()

    token_b, organization_id_b = await _signup_and_get_token(client, email="rls-b@example.com")

    async with session_scope(organization_id=organization_id_b) as session:
        runs_result = await session.execute(select(TestRun).where(TestRun.id == uuid.UUID(run_id_a)))
        assert runs_result.scalar_one_or_none() is None

        results_result = await session.execute(select(TestResult).where(TestResult.test_run_id == uuid.UUID(run_id_a)))
        assert results_result.scalars().all() == []

    # Confirm the rows genuinely exist under the correct org's own context —
    # the above emptiness is RLS isolation, not "nothing was ever written".
    async with session_scope(organization_id=organization_id_a) as session:
        own_result = await session.execute(select(TestResult).where(TestResult.test_run_id == uuid.UUID(run_id_a)))
        assert len(own_result.scalars().all()) == 1


async def test_creating_a_run_beyond_the_plan_limit_returns_402(client, fixture_site_url):
    """FR-123: the plan-limit check (test_executions metric, shared with
    billing/service.py's existing enforcement) actually blocks run creation
    rather than being wired but inert.

    `subscription_plans` is shared catalog data (one row per tier, not per
    Organization, and deliberately excluded from conftest's per-test
    TRUNCATE — see billing/service.py's set_plan_for_organization docstring
    and conftest.py's _clean_db comment). Mutating the free tier's row here
    would corrupt every other test's Organization on that tier for the rest
    of the session if not restored — so the original value is captured and
    put back in a finally block regardless of outcome.

    T220: this mutates the plan row directly (not via
    `billing_service.set_plan_for_organization`, the only path that calls
    `cache.invalidate` on write) specifically *because* going through that
    admin-only function would reassign every Organization on the tier's
    `plan_id`, which this test doesn't want — so it must invalidate the
    plan cache itself, both after its own write (this test's own earlier
    `_create_project` call already populated the cache with the
    pre-mutation limit) and after its restore (any later test's first read
    of this shared plan row must not see this test's `0` in the small
    window before the next test's own cache flush).
    """
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    case_id = await _create_approved_test_case(
        client, token, project_id, title="Case", steps=_relative_to_absolute(_PASSING_STEPS_A, fixture_site_url)
    )

    async with session_scope(organization_id=organization_id) as session:
        org_result = await session.execute(select(Organization).where(Organization.id == uuid.UUID(organization_id)))
        organization = org_result.scalar_one()
        plan_result = await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == organization.plan_id))
        plan = plan_result.scalar_one()
        plan_id = plan.id
        original_limit = plan.max_test_executions_per_period
        plan.max_test_executions_per_period = 0
        session.add(plan)
    await cache.invalidate(namespace="subscription_plan", key=str(plan_id))

    try:
        response = await client.post(
            f"/projects/{project_id}/test-runs", json={"test_case_ids": [case_id]}, headers=_auth_headers(token)
        )
        assert response.status_code == 402
        assert response.json()["error"]["code"] == "plan_limit_exceeded"
    finally:
        async with session_scope(organization_id=organization_id) as session:
            plan_result = await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id))
            plan = plan_result.scalar_one()
            plan.max_test_executions_per_period = original_limit
            session.add(plan)
        await cache.invalidate(namespace="subscription_plan", key=str(plan_id))
