"""Contract test for GET /organizations/current (contracts/organizations-api.md, T069)."""

import pytest


@pytest.mark.anyio
async def test_get_current_organization_requires_authentication(client):
    response = await client.get("/organizations/current")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_get_current_organization_returns_the_signed_up_organization(client):
    signup = await client.post(
        "/auth/signup",
        json={"email": "org-contract@example.com", "password": "correct horse battery staple", "name": "Org Test"},
    )
    token = signup.json()["access_token"]
    organization_id = signup.json()["organization"]["id"]

    response = await client.get("/organizations/current", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == organization_id
    assert body["name"] == "Org Test's Organization"
    assert body["plan"] == "free"
    assert body["slug"]
    assert body["created_at"]


@pytest.mark.anyio
async def test_get_current_organization_never_leaks_another_organization(client):
    """A second Organization's data must never be reachable through this
    endpoint — organizations has no RLS policy of its own (data-model.md),
    so this test is what actually proves the service layer's own
    current_user-derived scoping holds."""
    first = await client.post(
        "/auth/signup",
        json={"email": "org-a@example.com", "password": "correct horse battery staple", "name": "Org A"},
    )
    second = await client.post(
        "/auth/signup",
        json={"email": "org-b@example.com", "password": "correct horse battery staple", "name": "Org B"},
    )
    first_org_id = first.json()["organization"]["id"]
    second_org_id = second.json()["organization"]["id"]
    second_token = second.json()["access_token"]

    response = await client.get("/organizations/current", headers={"Authorization": f"Bearer {second_token}"})
    assert response.status_code == 200
    assert response.json()["id"] == second_org_id
    assert response.json()["id"] != first_org_id
