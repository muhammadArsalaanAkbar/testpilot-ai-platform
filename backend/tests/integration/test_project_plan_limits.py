"""Integration test: the free plan's max_projects=1 limit is actually
enforced end-to-end through the real API + Postgres (T087, FR-123, FR-125).
Unlike the contract tests (one endpoint's shape at a time), this proves the
billing library's check-and-persist round trip holds across two real
requests in the same Organization.
"""

import pytest


@pytest.mark.anyio
async def test_second_project_creation_is_blocked_at_the_free_plan_limit(client):
    signup = await client.post(
        "/auth/signup",
        json={"email": "plan-limit@example.com", "password": "correct horse battery staple", "name": "Plan Limit"},
    )
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    first = await client.post("/projects", json={"name": "First", "url": "https://example.com"}, headers=headers)
    assert first.status_code == 201

    second = await client.post("/projects", json={"name": "Second", "url": "https://example.com"}, headers=headers)
    assert second.status_code == 402
    body = second.json()
    assert body["error"]["code"] == "plan_limit_exceeded"
    assert body["error"]["details"]["limit"] == "projects"

    # The blocked attempt must not have been created.
    listing = await client.get("/projects", headers=headers)
    assert len(listing.json()["items"]) == 1


@pytest.mark.anyio
async def test_archiving_frees_a_slot_for_a_new_project(client):
    """Archiving is the user's way to free up a slot while keeping history
    (FR-028) — it must actually relieve the limit, not just hide the project."""
    signup = await client.post(
        "/auth/signup",
        json={
            "email": "plan-limit-archive@example.com",
            "password": "correct horse battery staple",
            "name": "Plan Limit Archive",
        },
    )
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    first = await client.post("/projects", json={"name": "First", "url": "https://example.com"}, headers=headers)
    assert first.status_code == 201
    project_id = first.json()["id"]

    blocked = await client.post("/projects", json={"name": "Second", "url": "https://example.com"}, headers=headers)
    assert blocked.status_code == 402

    archive = await client.post(f"/projects/{project_id}/archive", headers=headers)
    assert archive.status_code == 200

    now_allowed = await client.post(
        "/projects", json={"name": "Second (after archive)", "url": "https://example.com"}, headers=headers
    )
    assert now_allowed.status_code == 201
