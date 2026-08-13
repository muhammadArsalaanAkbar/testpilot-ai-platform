"""Contract tests for AI failure analysis endpoints (T156,
contracts/test-runs-api.md): the analyze endpoint, polling, and re-request
creating a new version. Job COMPLETION (a worker actually calling the LLM
provider and persisting a real analysis) is covered by
tests/integration/test_ai_analysis_failure.py and the CLI tests; these
contract tests cover the HTTP/enqueue layer against a real failed result
produced by the real Playwright engine (Phase 10/11), matching
test_test_runs.py's/test_test_results.py's precedent.
"""

import uuid

import pytest
from sqlalchemy import select

from testpilot.core.db import session_scope
from testpilot.execution import runner
from testpilot.execution.playwright_engine import PlaywrightEngine
from testpilot.projects.models import Project

pytestmark = pytest.mark.anyio


async def _public_resolver(hostname: str) -> list[str]:
    return ["8.8.8.8"]


async def _signup_and_get_token(client, email="ai-analysis-contract@example.com"):
    r = await client.post(
        "/auth/signup", json={"email": email, "password": "correct horse battery staple", "name": "Analysis Test"}
    )
    body = r.json()
    return body["access_token"], body["organization"]["id"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_project(client, token, name="Analysis Project"):
    r = await client.post("/projects", json={"name": name, "url": "https://example.com"}, headers=_auth_headers(token))
    return r.json()["id"]


async def _point_project_at_fixture_site(*, organization_id: str, project_id: str, fixture_site_url: str) -> None:
    async with session_scope(organization_id=organization_id) as session:
        result = await session.execute(select(Project).where(Project.id == uuid.UUID(project_id)))
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


async def _failed_result(client, token, organization_id, project_id, fixture_site_url):
    case_id = await _create_approved_test_case(
        client,
        token,
        project_id,
        title="Failing",
        steps=[
            {"action_type": "navigate", "target_descriptor": fixture_site_url},
            {"action_type": "assert_element", "target_descriptor": "#does-not-exist", "expected_assertion": "present"},
        ],
    )
    await _point_project_at_fixture_site(
        organization_id=organization_id, project_id=project_id, fixture_site_url=fixture_site_url
    )
    create = await client.post(
        f"/projects/{project_id}/test-runs", json={"test_case_ids": [case_id]}, headers=_auth_headers(token)
    )
    run_id = create.json()["id"]

    engine = PlaywrightEngine(url_resolver=_public_resolver)
    try:
        await runner.run_test_run(test_run_id=uuid.UUID(run_id), organization_id=uuid.UUID(organization_id), engine=engine)
    finally:
        await engine.close()

    detail = await client.get(f"/projects/{project_id}/test-runs/{run_id}", headers=_auth_headers(token))
    result_id = detail.json()["results"][0]["id"]
    return run_id, result_id


async def test_analyze_requires_authentication(client):
    response = await client.post(
        "/projects/00000000-0000-0000-0000-000000000000/test-runs/"
        "00000000-0000-0000-0000-000000000000/results/00000000-0000-0000-0000-000000000000/analyze"
    )
    assert response.status_code == 401


async def test_analyze_a_failed_result_returns_202_queued(client, fixture_site_url):
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    run_id, result_id = await _failed_result(client, token, organization_id, project_id, fixture_site_url)

    response = await client.post(
        f"/projects/{project_id}/test-runs/{run_id}/results/{result_id}/analyze", headers=_auth_headers(token)
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["test_result_id"] == result_id
    assert body["id"]
    assert body["explanation"] is None


async def test_analyze_a_passed_result_returns_409(client, fixture_site_url):
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    case_id = await _create_approved_test_case(
        client,
        token,
        project_id,
        title="Passing",
        steps=[
            {"action_type": "navigate", "target_descriptor": fixture_site_url},
            {"action_type": "assert_content", "expected_assertion": "Fixture Home"},
        ],
    )
    await _point_project_at_fixture_site(
        organization_id=organization_id, project_id=project_id, fixture_site_url=fixture_site_url
    )
    create = await client.post(
        f"/projects/{project_id}/test-runs", json={"test_case_ids": [case_id]}, headers=_auth_headers(token)
    )
    run_id = create.json()["id"]
    engine = PlaywrightEngine(url_resolver=_public_resolver)
    try:
        await runner.run_test_run(test_run_id=uuid.UUID(run_id), organization_id=uuid.UUID(organization_id), engine=engine)
    finally:
        await engine.close()
    detail = await client.get(f"/projects/{project_id}/test-runs/{run_id}", headers=_auth_headers(token))
    result_id = detail.json()["results"][0]["id"]

    response = await client.post(
        f"/projects/{project_id}/test-runs/{run_id}/results/{result_id}/analyze", headers=_auth_headers(token)
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "result_not_failed"


async def test_get_analysis_before_the_worker_processes_it_returns_404(client, fixture_site_url):
    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    run_id, result_id = await _failed_result(client, token, organization_id, project_id, fixture_site_url)
    trigger = await client.post(
        f"/projects/{project_id}/test-runs/{run_id}/results/{result_id}/analyze", headers=_auth_headers(token)
    )
    analysis_id = trigger.json()["id"]

    response = await client.get(
        f"/projects/{project_id}/test-runs/{run_id}/results/{result_id}/analyses/{analysis_id}",
        headers=_auth_headers(token),
    )

    assert response.status_code == 404


async def test_get_analysis_after_processing_returns_completed_status(client, fixture_site_url):
    from testpilot.ai_analysis import service as ai_analysis_service
    from testpilot.ai_provider.fake import FakeLLMProvider

    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    run_id, result_id = await _failed_result(client, token, organization_id, project_id, fixture_site_url)
    trigger = await client.post(
        f"/projects/{project_id}/test-runs/{run_id}/results/{result_id}/analyze", headers=_auth_headers(token)
    )
    analysis_id = trigger.json()["id"]

    await ai_analysis_service.run_analysis(
        ai_analysis_id=uuid.UUID(analysis_id),
        organization_id=uuid.UUID(organization_id),
        test_result_id=uuid.UUID(result_id),
        provider=FakeLLMProvider(),
        storage=None,
    )

    response = await client.get(
        f"/projects/{project_id}/test-runs/{run_id}/results/{result_id}/analyses/{analysis_id}",
        headers=_auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["explanation"]
    assert body["root_cause"]
    assert body["severity"] in ("minor", "major", "critical", "blocker")
    assert body["suggested_fix"]
    assert body["expected_vs_actual"]
    assert body["provider"]
    assert body["model"]


async def test_re_requesting_analysis_creates_a_new_version(client, fixture_site_url):
    from testpilot.ai_analysis import service as ai_analysis_service
    from testpilot.ai_provider.fake import FakeLLMProvider

    token, organization_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    run_id, result_id = await _failed_result(client, token, organization_id, project_id, fixture_site_url)

    first_trigger = await client.post(
        f"/projects/{project_id}/test-runs/{run_id}/results/{result_id}/analyze", headers=_auth_headers(token)
    )
    first_id = first_trigger.json()["id"]
    await ai_analysis_service.run_analysis(
        ai_analysis_id=uuid.UUID(first_id), organization_id=uuid.UUID(organization_id),
        test_result_id=uuid.UUID(result_id), provider=FakeLLMProvider(), storage=None,
    )

    second_trigger = await client.post(
        f"/projects/{project_id}/test-runs/{run_id}/results/{result_id}/analyze", headers=_auth_headers(token)
    )
    second_id = second_trigger.json()["id"]
    assert second_id != first_id
    await ai_analysis_service.run_analysis(
        ai_analysis_id=uuid.UUID(second_id), organization_id=uuid.UUID(organization_id),
        test_result_id=uuid.UUID(result_id), provider=FakeLLMProvider(), storage=None,
    )

    result_detail = await client.get(
        f"/projects/{project_id}/test-runs/{run_id}/results/{result_id}", headers=_auth_headers(token)
    )
    analyses = result_detail.json()["ai_analyses"]
    assert len(analyses) == 2
    # Most recent first (FR-085's versioning).
    assert analyses[0]["id"] == second_id
    assert analyses[1]["id"] == first_id


async def test_analysis_from_another_organization_is_not_found(client, fixture_site_url):
    """FR-138/SEC-011: cross-tenant access returns 404, never 403."""
    token_a, organization_id_a = await _signup_and_get_token(client, email="analysis-org-a@example.com")
    project_id_a = await _create_project(client, token_a)
    run_id_a, result_id_a = await _failed_result(client, token_a, organization_id_a, project_id_a, fixture_site_url)
    trigger = await client.post(
        f"/projects/{project_id_a}/test-runs/{run_id_a}/results/{result_id_a}/analyze", headers=_auth_headers(token_a)
    )
    analysis_id_a = trigger.json()["id"]

    token_b, _org_b = await _signup_and_get_token(client, email="analysis-org-b@example.com")
    project_id_b = await _create_project(client, token_b)

    response = await client.get(
        f"/projects/{project_id_b}/test-runs/{run_id_a}/results/{result_id_a}/analyses/{analysis_id_a}",
        headers=_auth_headers(token_b),
    )
    assert response.status_code == 404
