"""Contract tests for the Notifications API (T189, contracts/notifications-api.md):
list/read/read-all, plus real notification creation via the execute_test_run
and analyze_failure worker-job code paths (T192) — not seeded directly,
since the point of these tests is to prove the actual trigger wiring works.
"""

import uuid

import pytest
from sqlalchemy import select

from testpilot.ai_analysis import service as ai_analysis_service
from testpilot.ai_provider.fake import FakeLLMProvider
from testpilot.core.db import session_scope
from testpilot.execution import runner
from testpilot.execution.playwright_engine import PlaywrightEngine
from testpilot.projects.models import Project

pytestmark = pytest.mark.anyio


async def _public_resolver(hostname: str) -> list[str]:
    return ["8.8.8.8"]


async def _signup_and_get_token(client, email="notifications-contract@example.com"):
    r = await client.post(
        "/auth/signup",
        json={"email": email, "password": "correct horse battery staple", "name": "Notifications Test"},
    )
    body = r.json()
    return body["access_token"], body["organization"]["id"], body["user"]["id"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_project(client, token, name="Notifications Project"):
    r = await client.post(
        "/projects", json={"name": name, "url": "https://example.com"}, headers=_auth_headers(token)
    )
    return r.json()["id"]


async def _point_project_at_fixture_site(*, organization_id: str, project_id: str, fixture_site_url: str) -> None:
    async with session_scope(organization_id=organization_id) as session:
        result = await session.execute(select(Project).where(Project.id == uuid.UUID(project_id)))
        project = result.scalar_one()
        project.url = fixture_site_url
        session.add(project)


async def _create_approved_test_case(client, token, project_id, *, title, steps):
    r = await client.post(
        f"/projects/{project_id}/test-cases",
        json={"title": title, "description": "d", "priority": "high", "severity": "critical", "steps": steps},
        headers=_auth_headers(token),
    )
    case_id = r.json()["id"]
    await client.post(f"/projects/{project_id}/test-cases/{case_id}/approve", headers=_auth_headers(token))
    return case_id


async def _run_a_failing_case(client, token, organization_id, project_id, fixture_site_url):
    """A real run with one critical-severity case that fails, driven
    through the real orchestrator (not seeded) -- this is what actually
    exercises T192's run_completed/run_failed_critical notification wiring."""
    case_id = await _create_approved_test_case(
        client,
        token,
        project_id,
        title="Failing critical case",
        steps=[
            {"action_type": "navigate", "target_descriptor": fixture_site_url},
            {"action_type": "assert_element", "target_descriptor": "#does-not-exist", "expected_assertion": "present"},
        ],
    )
    await _point_project_at_fixture_site(
        organization_id=organization_id, project_id=project_id, fixture_site_url=fixture_site_url
    )
    run_response = await client.post(
        f"/projects/{project_id}/test-runs", json={"test_case_ids": [case_id]}, headers=_auth_headers(token)
    )
    run_id = run_response.json()["id"]

    engine = PlaywrightEngine(url_resolver=_public_resolver)
    try:
        await runner.run_test_run(
            test_run_id=uuid.UUID(run_id), organization_id=uuid.UUID(organization_id), engine=engine
        )
    finally:
        await engine.close()
    return run_id


async def test_notifications_list_is_empty_before_anything_happens(client):
    token, _organization_id, _user_id = await _signup_and_get_token(client)
    response = await client.get("/notifications", headers=_auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body == {"items": [], "unread_count": 0}


async def test_notifications_requires_authentication(client):
    response = await client.get("/notifications")
    assert response.status_code == 401


async def test_completing_a_run_with_a_critical_failure_creates_a_flagged_notification(
    client, fixture_site_url
):
    token, organization_id, user_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    run_id = await _run_a_failing_case(client, token, organization_id, project_id, fixture_site_url)

    response = await client.get("/notifications", headers=_auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["unread_count"] == 1
    assert len(body["items"]) == 1

    notification = body["items"][0]
    assert notification["type"] == "run_failed_critical"
    assert notification["related_entity_type"] == "test_run"
    assert notification["related_entity_id"] == run_id
    assert notification["project_id"] == project_id
    assert notification["read_at"] is None


async def test_mark_read_is_idempotent(client, fixture_site_url):
    token, organization_id, user_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    await _run_a_failing_case(client, token, organization_id, project_id, fixture_site_url)

    list_response = await client.get("/notifications", headers=_auth_headers(token))
    notification_id = list_response.json()["items"][0]["id"]

    first = await client.post(f"/notifications/{notification_id}/read", headers=_auth_headers(token))
    assert first.status_code == 200
    assert first.json()["notification"]["read_at"] is not None

    second = await client.post(f"/notifications/{notification_id}/read", headers=_auth_headers(token))
    assert second.status_code == 200
    assert second.json()["notification"]["read_at"] == first.json()["notification"]["read_at"]

    unread_response = await client.get("/notifications?unread_only=true", headers=_auth_headers(token))
    assert unread_response.json()["items"] == []


async def test_mark_read_returns_404_for_a_nonexistent_notification(client):
    token, _organization_id, _user_id = await _signup_and_get_token(client)
    response = await client.post(f"/notifications/{uuid.uuid4()}/read", headers=_auth_headers(token))
    assert response.status_code == 404


async def test_read_all_marks_every_notification_read(client, fixture_site_url):
    token, organization_id, user_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    await _run_a_failing_case(client, token, organization_id, project_id, fixture_site_url)
    await _run_a_failing_case(client, token, organization_id, project_id, fixture_site_url)

    before = await client.get("/notifications", headers=_auth_headers(token))
    assert before.json()["unread_count"] == 2

    read_all_response = await client.post("/notifications/read-all", headers=_auth_headers(token))
    assert read_all_response.status_code == 204

    after = await client.get("/notifications", headers=_auth_headers(token))
    assert after.json()["unread_count"] == 0


async def test_completing_an_ai_analysis_notifies_the_run_initiator(client, fixture_site_url):
    token, organization_id, user_id = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    run_id = await _run_a_failing_case(client, token, organization_id, project_id, fixture_site_url)

    run_detail = await client.get(f"/projects/{project_id}/test-runs/{run_id}", headers=_auth_headers(token))
    test_result_id = run_detail.json()["results"][0]["id"]

    ai_analysis_id = uuid.uuid4()
    await ai_analysis_service.run_analysis(
        ai_analysis_id=ai_analysis_id,
        organization_id=uuid.UUID(organization_id),
        test_result_id=uuid.UUID(test_result_id),
        provider=FakeLLMProvider(),
        storage=None,
    )

    response = await client.get("/notifications", headers=_auth_headers(token))
    types = {item["type"] for item in response.json()["items"]}
    assert "ai_analysis_completed" in types

    analysis_notification = next(item for item in response.json()["items"] if item["type"] == "ai_analysis_completed")
    assert analysis_notification["related_entity_type"] == "test_result"
    assert analysis_notification["related_entity_id"] == test_result_id
    assert analysis_notification["project_id"] == project_id
    assert analysis_notification["test_run_id"] == run_id


async def test_notifications_are_isolated_per_organization(client, fixture_site_url):
    token_a, organization_a, _user_a = await _signup_and_get_token(client, email="notif-org-a@example.com")
    project_a = await _create_project(client, token_a)
    await _run_a_failing_case(client, token_a, organization_a, project_a, fixture_site_url)

    token_b, _organization_b, _user_b = await _signup_and_get_token(client, email="notif-org-b@example.com")
    response = await client.get("/notifications", headers=_auth_headers(token_b))
    assert response.json() == {"items": [], "unread_count": 0}
