"""Integration test: the analysis-unavailable path when the provider is
mocked to fail (T157, FR-083). Directly invokes `ai_analysis.service.run_analysis`
— the exact function the real worker calls via `worker/jobs/analyze_failure.py`'s
`handle` — against a real failed TestResult produced by the real Playwright
engine, with the `FakeLLMProvider`'s documented `fail_mode` standing in for a
real provider outage (the same fake-provider-failure-injection pattern
test_ai_generation_flow.py already establishes for generation).
"""

import uuid

import pytest
from sqlalchemy import select

from testpilot.ai_analysis import service as ai_analysis_service
from testpilot.ai_analysis.models import AIAnalysis, AIAnalysisStatus
from testpilot.ai_provider.fake import FakeLLMProvider
from testpilot.core.db import session_scope
from testpilot.execution import runner
from testpilot.execution.playwright_engine import PlaywrightEngine
from testpilot.projects.models import Project

pytestmark = pytest.mark.anyio


async def _public_resolver(hostname: str) -> list[str]:
    return ["8.8.8.8"]


async def _signup_and_get_token(client, email="ai-analysis-failure@example.com"):
    r = await client.post(
        "/auth/signup", json={"email": email, "password": "correct horse battery staple", "name": "Analysis Fail Test"}
    )
    body = r.json()
    return body["access_token"], body["organization"]["id"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_project(client, token, name="Analysis Fail Project"):
    r = await client.post("/projects", json={"name": name, "url": "https://example.com"}, headers=_auth_headers(token))
    return r.json()["id"]


async def _point_project_at_fixture_site(*, organization_id: str, project_id: str, fixture_site_url: str) -> None:
    async with session_scope(organization_id=organization_id) as session:
        result = await session.execute(select(Project).where(Project.id == uuid.UUID(project_id)))
        project = result.scalar_one()
        project.url = fixture_site_url
        session.add(project)


async def _failed_result(client, token, organization_id, project_id, fixture_site_url):
    create = await client.post(
        f"/projects/{project_id}/test-cases",
        json={
            "title": "Failing",
            "description": "D",
            "priority": "low",
            "severity": "minor",
            "steps": [
                {"action_type": "navigate", "target_descriptor": fixture_site_url},
                {"action_type": "assert_element", "target_descriptor": "#does-not-exist", "expected_assertion": "present"},
            ],
        },
        headers=_auth_headers(token),
    )
    case_id = create.json()["id"]
    await client.post(f"/projects/{project_id}/test-cases/{case_id}/approve", headers=_auth_headers(token))
    await _point_project_at_fixture_site(
        organization_id=organization_id, project_id=project_id, fixture_site_url=fixture_site_url
    )

    run_create = await client.post(
        f"/projects/{project_id}/test-runs", json={"test_case_ids": [case_id]}, headers=_auth_headers(token)
    )
    run_id = run_create.json()["id"]
    engine = PlaywrightEngine(url_resolver=_public_resolver)
    try:
        await runner.run_test_run(test_run_id=uuid.UUID(run_id), organization_id=uuid.UUID(organization_id), engine=engine)
    finally:
        await engine.close()

    detail = await client.get(f"/projects/{project_id}/test-runs/{run_id}", headers=_auth_headers(token))
    return detail.json()["results"][0]["id"]


async def test_provider_timeout_produces_a_distinct_unavailable_state_not_a_fabricated_result(client, fixture_site_url):
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    result_id = await _failed_result(client, token, organization_id, project_id, fixture_site_url)

    analysis_id = uuid.uuid4()
    await ai_analysis_service.run_analysis(
        ai_analysis_id=analysis_id,
        organization_id=uuid.UUID(organization_id),
        test_result_id=uuid.UUID(result_id),
        provider=FakeLLMProvider(fail_mode="timeout"),
        storage=None,
    )

    async with session_scope(organization_id=organization_id) as session:
        result = await session.execute(select(AIAnalysis).where(AIAnalysis.id == analysis_id))
        analysis = result.scalar_one()

    assert analysis.status == AIAnalysisStatus.failed
    assert analysis.failure_reason
    assert analysis.explanation is None
    assert analysis.root_cause is None
    assert analysis.suggested_fix is None


async def test_provider_malformed_output_also_produces_a_failed_analysis_not_a_retry_storm(client, fixture_site_url):
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    result_id = await _failed_result(client, token, organization_id, project_id, fixture_site_url)

    analysis_id = uuid.uuid4()
    provider = FakeLLMProvider(fail_mode="malformed")
    await ai_analysis_service.run_analysis(
        ai_analysis_id=analysis_id,
        organization_id=uuid.UUID(organization_id),
        test_result_id=uuid.UUID(result_id),
        provider=provider,
        storage=None,
    )

    async with session_scope(organization_id=organization_id) as session:
        result = await session.execute(select(AIAnalysis).where(AIAnalysis.id == analysis_id))
        analysis = result.scalar_one()
    assert analysis.status == AIAnalysisStatus.failed


async def test_a_transient_timeout_is_retried_within_a_bounded_limit_then_can_still_succeed(client, fixture_site_url):
    """FR-083: a bounded retry policy — a provider that fails once with a
    retryable error and then succeeds must still produce a completed
    analysis, not immediately give up on the first failure."""
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    result_id = await _failed_result(client, token, organization_id, project_id, fixture_site_url)

    class _FlakyOnceProvider(FakeLLMProvider):
        def __init__(self) -> None:
            super().__init__()
            self._calls = 0

        async def analyze_failure(self, context):  # type: ignore[override]
            self._calls += 1
            if self._calls == 1:
                from testpilot.ai_provider.base import AIProviderError

                raise AIProviderError("simulated transient timeout", retryable=True)
            return await super().analyze_failure(context)

    analysis_id = uuid.uuid4()
    flaky_provider = _FlakyOnceProvider()
    await ai_analysis_service.run_analysis(
        ai_analysis_id=analysis_id,
        organization_id=uuid.UUID(organization_id),
        test_result_id=uuid.UUID(result_id),
        provider=flaky_provider,
        storage=None,
    )

    assert flaky_provider._calls == 2
    async with session_scope(organization_id=organization_id) as session:
        result = await session.execute(select(AIAnalysis).where(AIAnalysis.id == analysis_id))
        analysis = result.scalar_one()
    assert analysis.status == AIAnalysisStatus.completed
    assert analysis.explanation


async def test_a_non_retryable_error_fails_immediately_without_retrying(client, fixture_site_url):
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    result_id = await _failed_result(client, token, organization_id, project_id, fixture_site_url)

    class _CountingProvider(FakeLLMProvider):
        def __init__(self) -> None:
            super().__init__(fail_mode="malformed")
            self.calls = 0

        async def analyze_failure(self, context):  # type: ignore[override]
            self.calls += 1
            return await super().analyze_failure(context)

    analysis_id = uuid.uuid4()
    provider = _CountingProvider()
    await ai_analysis_service.run_analysis(
        ai_analysis_id=analysis_id,
        organization_id=uuid.UUID(organization_id),
        test_result_id=uuid.UUID(result_id),
        provider=provider,
        storage=None,
    )

    # malformed output -> AIProviderError(retryable=False) -> exactly one attempt.
    assert provider.calls == 1


async def test_analysis_unavailable_result_is_still_queryable_via_the_api(client, fixture_site_url):
    """FR-084/FR-083: even a failed analysis must be persisted and visible
    later, distinguishing "no analysis requested" from "analysis failed"."""
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    result_id = await _failed_result(client, token, organization_id, project_id, fixture_site_url)

    analysis_id = uuid.uuid4()
    await ai_analysis_service.run_analysis(
        ai_analysis_id=analysis_id,
        organization_id=uuid.UUID(organization_id),
        test_result_id=uuid.UUID(result_id),
        provider=FakeLLMProvider(fail_mode="timeout"),
        storage=None,
    )

    run_list = await client.get(f"/projects/{project_id}/test-runs", headers=_auth_headers(token))
    run_id = run_list.json()["items"][0]["id"]

    response = await client.get(
        f"/projects/{project_id}/test-runs/{run_id}/results/{result_id}/analyses/{analysis_id}",
        headers=_auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["failure_reason"]
