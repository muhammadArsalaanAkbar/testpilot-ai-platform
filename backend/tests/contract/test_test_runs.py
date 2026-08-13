"""Contract tests for Test Runs endpoints (T134, contracts/test-runs-api.md).

These cover the HTTP/enqueue layer only — job COMPLETION (a worker actually
driving a real browser through Playwright and producing genuine pass/fail
results) is verified by tests/integration/test_execution_flow.py (T135),
mirroring how test_ai_generation.py/test_ai_generation_flow.py split the
same concern for the generation feature.
"""

import pytest

pytestmark = pytest.mark.anyio


async def _signup_and_get_token(client, email="test-runs-contract@example.com"):
    r = await client.post(
        "/auth/signup", json={"email": email, "password": "correct horse battery staple", "name": "Test Runs Test"}
    )
    return r.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_project(client, token, name="Test Runs Project"):
    r = await client.post("/projects", json={"name": name, "url": "https://example.com"}, headers=_auth_headers(token))
    return r.json()["id"]


async def _create_approved_test_case(client, token, project_id, title="Case"):
    create = await client.post(
        f"/projects/{project_id}/test-cases",
        json={
            "title": title,
            "description": "D",
            "priority": "low",
            "severity": "minor",
            "steps": [{"action_type": "navigate", "target_descriptor": "https://example.com"}],
        },
        headers=_auth_headers(token),
    )
    test_case_id = create.json()["id"]
    await client.post(f"/projects/{project_id}/test-cases/{test_case_id}/approve", headers=_auth_headers(token))
    return test_case_id


async def test_create_test_run_requires_authentication(client):
    response = await client.post(
        "/projects/00000000-0000-0000-0000-000000000000/test-runs", json={"test_case_ids": []}
    )
    assert response.status_code == 401


async def test_create_test_run_returns_202_with_a_queued_run(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    case_id = await _create_approved_test_case(client, token, project_id)

    response = await client.post(
        f"/projects/{project_id}/test-runs", json={"test_case_ids": [case_id]}, headers=_auth_headers(token)
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["project_id"] == project_id
    assert body["summary_total"] == 1
    assert body["summary_passed"] == 0
    assert body["summary_failed"] == 0
    assert body["summary_skipped"] == 0
    assert body["started_at"] is None
    assert body["completed_at"] is None
    assert body["id"]


async def test_create_test_run_for_archived_project_returns_409(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    case_id = await _create_approved_test_case(client, token, project_id)
    await client.post(f"/projects/{project_id}/archive", headers=_auth_headers(token))

    response = await client.post(
        f"/projects/{project_id}/test-runs", json={"test_case_ids": [case_id]}, headers=_auth_headers(token)
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "project_archived"


async def test_create_test_run_rejects_a_rejected_status_case(client):
    """FR-057: a rejected-status case can never be selected into a new run."""
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    create = await client.post(
        f"/projects/{project_id}/test-cases",
        json={"title": "Rejected case", "description": "D", "priority": "low", "severity": "minor"},
        headers=_auth_headers(token),
    )
    case_id = create.json()["id"]
    await client.post(f"/projects/{project_id}/test-cases/{case_id}/reject", headers=_auth_headers(token))

    response = await client.post(
        f"/projects/{project_id}/test-runs", json={"test_case_ids": [case_id]}, headers=_auth_headers(token)
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "no_approved_cases_selected"


async def test_create_test_run_with_unknown_case_id_returns_404(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    response = await client.post(
        f"/projects/{project_id}/test-runs",
        json={"test_case_ids": ["00000000-0000-0000-0000-000000000000"]},
        headers=_auth_headers(token),
    )

    assert response.status_code == 404


async def test_list_test_runs(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    case_id = await _create_approved_test_case(client, token, project_id)
    await client.post(
        f"/projects/{project_id}/test-runs", json={"test_case_ids": [case_id]}, headers=_auth_headers(token)
    )

    response = await client.get(f"/projects/{project_id}/test-runs", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["project_id"] == project_id


async def test_get_test_run(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    case_id = await _create_approved_test_case(client, token, project_id)
    create = await client.post(
        f"/projects/{project_id}/test-runs", json={"test_case_ids": [case_id]}, headers=_auth_headers(token)
    )
    run_id = create.json()["id"]

    response = await client.get(f"/projects/{project_id}/test-runs/{run_id}", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["test_run"]["id"] == run_id
    assert body["results"] == []


async def test_get_nonexistent_test_run_returns_404(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    response = await client.get(
        f"/projects/{project_id}/test-runs/00000000-0000-0000-0000-000000000000", headers=_auth_headers(token)
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_retry_failed_on_a_non_terminal_run_returns_409(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    case_id = await _create_approved_test_case(client, token, project_id)
    create = await client.post(
        f"/projects/{project_id}/test-runs", json={"test_case_ids": [case_id]}, headers=_auth_headers(token)
    )
    run_id = create.json()["id"]

    response = await client.post(
        f"/projects/{project_id}/test-runs/{run_id}/retry-failed", headers=_auth_headers(token)
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "run_not_completed"


async def test_retry_failed_on_nonexistent_run_returns_404(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    response = await client.post(
        f"/projects/{project_id}/test-runs/00000000-0000-0000-0000-000000000000/retry-failed",
        headers=_auth_headers(token),
    )

    assert response.status_code == 404


async def test_test_run_from_another_organization_is_not_found(client):
    """FR-138/SEC-011: cross-tenant access returns 404, never 403."""
    token_a = await _signup_and_get_token(client, email="org-a@example.com")
    project_id_a = await _create_project(client, token_a)
    case_id_a = await _create_approved_test_case(client, token_a, project_id_a)
    create = await client.post(
        f"/projects/{project_id_a}/test-runs", json={"test_case_ids": [case_id_a]}, headers=_auth_headers(token_a)
    )
    run_id_a = create.json()["id"]

    token_b = await _signup_and_get_token(client, email="org-b@example.com")
    project_id_b = await _create_project(client, token_b)

    response = await client.get(
        f"/projects/{project_id_b}/test-runs/{run_id_a}", headers=_auth_headers(token_b)
    )
    assert response.status_code == 404
