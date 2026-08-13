"""Contract tests for the Test Cases API (contracts/test-cases-api.md, T098).

Only library CRUD/approve/reject/list/filter/search is covered here — the
AI generation endpoints on the same router (POST .../generate and friends)
are Phase 9's scope (see api/v1/testcases.py's module docstring).
"""

import pytest


async def _signup_and_get_token(client, email="testcases-contract@example.com"):
    r = await client.post(
        "/auth/signup", json={"email": email, "password": "correct horse battery staple", "name": "Test Cases Test"}
    )
    return r.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_project(client, token, name="TC Project"):
    r = await client.post("/projects", json={"name": name, "url": "https://example.com"}, headers=_auth_headers(token))
    return r.json()["id"]


@pytest.mark.anyio
async def test_create_test_case_requires_authentication(client):
    response = await client.post("/projects/00000000-0000-0000-0000-000000000000/test-cases", json={})
    assert response.status_code == 401


@pytest.mark.anyio
async def test_create_manual_test_case_succeeds(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    response = await client.post(
        f"/projects/{project_id}/test-cases",
        json={
            "title": "Login with valid credentials",
            "description": "Verify a user can log in with a correct email/password.",
            "priority": "high",
            "severity": "major",
            "tags": ["auth", "smoke"],
            "steps": [
                {"action_type": "navigate", "target_descriptor": "/login"},
                {"action_type": "type", "target_descriptor": "#email", "input_value": "user@example.com"},
                {"action_type": "submit", "target_descriptor": "#login-form"},
                {"action_type": "assert_url", "expected_assertion": "/dashboard"},
            ],
        },
        headers=_auth_headers(token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Login with valid credentials"
    assert body["status"] == "draft"
    assert body["source"] == "manual"
    assert body["last_result"] == "not_run"
    assert set(body["tags"]) == {"auth", "smoke"}

    detail = await client.get(f"/projects/{project_id}/test-cases/{body['id']}", headers=_auth_headers(token))
    assert detail.status_code == 200
    steps = detail.json()["steps"]
    assert len(steps) == 4
    assert steps[0]["order_index"] == 0
    assert steps[0]["action_type"] == "navigate"
    assert steps[3]["action_type"] == "assert_url"
    assert detail.json()["recent_results"] == []


@pytest.mark.anyio
async def test_create_test_case_rejects_invalid_body(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    response = await client.post(
        f"/projects/{project_id}/test-cases", json={"title": "", "description": "x"}, headers=_auth_headers(token)
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_create_test_case_in_archived_project_is_blocked(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    await client.post(f"/projects/{project_id}/archive", headers=_auth_headers(token))

    response = await client.post(
        f"/projects/{project_id}/test-cases",
        json={"title": "T", "description": "D", "priority": "low", "severity": "minor"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "project_archived"


@pytest.mark.anyio
async def test_get_nonexistent_test_case_returns_404(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    response = await client.get(
        f"/projects/{project_id}/test-cases/00000000-0000-0000-0000-000000000000", headers=_auth_headers(token)
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.anyio
async def test_test_case_from_another_organization_is_not_found(client):
    token_a = await _signup_and_get_token(client, email="tc-org-a@example.com")
    project_id_a = await _create_project(client, token_a, name="Org A Project")
    create = await client.post(
        f"/projects/{project_id_a}/test-cases",
        json={"title": "T", "description": "D", "priority": "low", "severity": "minor"},
        headers=_auth_headers(token_a),
    )
    test_case_id = create.json()["id"]

    token_b = await _signup_and_get_token(client, email="tc-org-b@example.com")
    project_id_b = await _create_project(client, token_b, name="Org B Project")
    response = await client.get(
        f"/projects/{project_id_b}/test-cases/{test_case_id}", headers=_auth_headers(token_b)
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_update_test_case_edits_fields_and_replaces_steps(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    create = await client.post(
        f"/projects/{project_id}/test-cases",
        json={
            "title": "Old title",
            "description": "D",
            "priority": "low",
            "severity": "minor",
            "steps": [{"action_type": "navigate", "target_descriptor": "/"}],
        },
        headers=_auth_headers(token),
    )
    test_case_id = create.json()["id"]

    response = await client.patch(
        f"/projects/{project_id}/test-cases/{test_case_id}",
        json={
            "title": "New title",
            "priority": "critical",
            "steps": [
                {"action_type": "navigate", "target_descriptor": "/new"},
                {"action_type": "click", "target_descriptor": "#button"},
            ],
        },
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "New title"
    assert body["priority"] == "critical"
    assert body["description"] == "D"
    assert body["source"] == "manual"

    detail = await client.get(f"/projects/{project_id}/test-cases/{test_case_id}", headers=_auth_headers(token))
    steps = detail.json()["steps"]
    assert len(steps) == 2
    assert steps[1]["action_type"] == "click"


@pytest.mark.anyio
async def test_approve_then_reject_transitions(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    create = await client.post(
        f"/projects/{project_id}/test-cases",
        json={"title": "T", "description": "D", "priority": "low", "severity": "minor"},
        headers=_auth_headers(token),
    )
    test_case_id = create.json()["id"]

    approve = await client.post(f"/projects/{project_id}/test-cases/{test_case_id}/approve", headers=_auth_headers(token))
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"

    reject = await client.post(f"/projects/{project_id}/test-cases/{test_case_id}/reject", headers=_auth_headers(token))
    assert reject.status_code == 200
    assert reject.json()["status"] == "rejected"


@pytest.mark.anyio
async def test_delete_test_case_succeeds(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    create = await client.post(
        f"/projects/{project_id}/test-cases",
        json={"title": "T", "description": "D", "priority": "low", "severity": "minor"},
        headers=_auth_headers(token),
    )
    test_case_id = create.json()["id"]

    response = await client.delete(f"/projects/{project_id}/test-cases/{test_case_id}", headers=_auth_headers(token))
    assert response.status_code == 204

    get_response = await client.get(f"/projects/{project_id}/test-cases/{test_case_id}", headers=_auth_headers(token))
    assert get_response.status_code == 404


@pytest.mark.anyio
async def test_list_filters_by_status_priority_severity_tag_and_source(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    high = await client.post(
        f"/projects/{project_id}/test-cases",
        json={"title": "High prio", "description": "D", "priority": "high", "severity": "major", "tags": ["billing"]},
        headers=_auth_headers(token),
    )
    low = await client.post(
        f"/projects/{project_id}/test-cases",
        json={"title": "Low prio", "description": "D", "priority": "low", "severity": "minor", "tags": ["ui"]},
        headers=_auth_headers(token),
    )
    high_id = high.json()["id"]
    low_id = low.json()["id"]
    await client.post(f"/projects/{project_id}/test-cases/{high_id}/approve", headers=_auth_headers(token))

    by_priority = await client.get(f"/projects/{project_id}/test-cases?priority=high", headers=_auth_headers(token))
    ids = {c["id"] for c in by_priority.json()["items"]}
    assert ids == {high_id}

    by_severity = await client.get(f"/projects/{project_id}/test-cases?severity=minor", headers=_auth_headers(token))
    assert {c["id"] for c in by_severity.json()["items"]} == {low_id}

    by_status = await client.get(f"/projects/{project_id}/test-cases?status_filter=approved", headers=_auth_headers(token))
    assert {c["id"] for c in by_status.json()["items"]} == {high_id}

    by_tag = await client.get(f"/projects/{project_id}/test-cases?tag=ui", headers=_auth_headers(token))
    assert {c["id"] for c in by_tag.json()["items"]} == {low_id}

    by_source = await client.get(f"/projects/{project_id}/test-cases?source=manual", headers=_auth_headers(token))
    assert {c["id"] for c in by_source.json()["items"]} == {high_id, low_id}


@pytest.mark.anyio
async def test_list_full_text_search(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    match = await client.post(
        f"/projects/{project_id}/test-cases",
        json={"title": "Checkout flow", "description": "Verify the shopping cart checkout completes.", "priority": "high", "severity": "major"},
        headers=_auth_headers(token),
    )
    await client.post(
        f"/projects/{project_id}/test-cases",
        json={"title": "Profile update", "description": "Verify a user can update their profile picture.", "priority": "low", "severity": "minor"},
        headers=_auth_headers(token),
    )
    match_id = match.json()["id"]

    response = await client.get(f"/projects/{project_id}/test-cases?q=checkout", headers=_auth_headers(token))
    assert response.status_code == 200
    ids = {c["id"] for c in response.json()["items"]}
    assert ids == {match_id}


@pytest.mark.anyio
async def test_list_sort_by_priority_ascending_and_descending(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    for title, priority in [("A", "low"), ("B", "critical"), ("C", "medium")]:
        await client.post(
            f"/projects/{project_id}/test-cases",
            json={"title": title, "description": "D", "priority": priority, "severity": "minor"},
            headers=_auth_headers(token),
        )

    ascending = await client.get(f"/projects/{project_id}/test-cases?sort=priority", headers=_auth_headers(token))
    assert [c["priority"] for c in ascending.json()["items"]] == ["low", "medium", "critical"]

    descending = await client.get(f"/projects/{project_id}/test-cases?sort=-priority", headers=_auth_headers(token))
    assert [c["priority"] for c in descending.json()["items"]] == ["critical", "medium", "low"]
