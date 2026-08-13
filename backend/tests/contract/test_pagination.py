"""Contract tests for the shared pagination helper (T197, contracts/_conventions.md):
`?page=&page_size=` bounds/defaults applied consistently, and real
page-size-bounded slicing on the test-cases list endpoint — a genuine gap
before this task (test-cases-api.md documents it "(paginated)" but the
endpoint previously returned every matching row unbounded).
"""

import pytest


async def _signup_and_get_token(client, email="pagination-contract@example.com"):
    r = await client.post(
        "/auth/signup", json={"email": email, "password": "correct horse battery staple", "name": "Pagination Test"}
    )
    return r.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_project(client, token, name="Pagination Project"):
    r = await client.post("/projects", json={"name": name, "url": "https://example.com"}, headers=_auth_headers(token))
    return r.json()["id"]


async def _create_test_case(client, token, project_id, title):
    r = await client.post(
        f"/projects/{project_id}/test-cases",
        json={
            "title": title,
            "description": "d",
            "priority": "medium",
            "severity": "minor",
            "steps": [{"action_type": "navigate", "target_descriptor": "/"}],
        },
        headers=_auth_headers(token),
    )
    return r.json()["id"]


@pytest.mark.anyio
async def test_test_cases_list_honors_page_size(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    for i in range(30):
        await _create_test_case(client, token, project_id, f"Case {i:02d}")

    response = await client.get(
        f"/projects/{project_id}/test-cases?page=1&page_size=10", headers=_auth_headers(token)
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 10


@pytest.mark.anyio
async def test_test_cases_list_second_page_returns_different_items(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    for i in range(30):
        await _create_test_case(client, token, project_id, f"Case {i:02d}")

    page1 = await client.get(f"/projects/{project_id}/test-cases?page=1&page_size=10", headers=_auth_headers(token))
    page2 = await client.get(f"/projects/{project_id}/test-cases?page=2&page_size=10", headers=_auth_headers(token))
    page3 = await client.get(f"/projects/{project_id}/test-cases?page=3&page_size=10", headers=_auth_headers(token))
    page4 = await client.get(f"/projects/{project_id}/test-cases?page=4&page_size=10", headers=_auth_headers(token))

    ids_1 = {c["id"] for c in page1.json()["items"]}
    ids_2 = {c["id"] for c in page2.json()["items"]}
    ids_3 = {c["id"] for c in page3.json()["items"]}
    assert ids_1.isdisjoint(ids_2)
    assert ids_1.isdisjoint(ids_3)
    assert ids_2.isdisjoint(ids_3)
    assert len(page4.json()["items"]) == 0


@pytest.mark.anyio
async def test_test_cases_list_defaults_to_page_size_25(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)
    for i in range(30):
        await _create_test_case(client, token, project_id, f"Case {i:02d}")

    response = await client.get(f"/projects/{project_id}/test-cases", headers=_auth_headers(token))
    assert response.status_code == 200
    assert len(response.json()["items"]) == 25


@pytest.mark.anyio
async def test_test_cases_list_rejects_page_size_over_100(client):
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    response = await client.get(
        f"/projects/{project_id}/test-cases?page_size=101", headers=_auth_headers(token)
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_test_runs_list_rejects_page_size_over_100(client):
    """Same bound, applied to the endpoint pagination.py's helper already
    served before this task -- proves both endpoints share one definition."""
    token = await _signup_and_get_token(client)
    project_id = await _create_project(client, token)

    response = await client.get(
        f"/projects/{project_id}/test-runs?page_size=101", headers=_auth_headers(token)
    )
    assert response.status_code == 422
