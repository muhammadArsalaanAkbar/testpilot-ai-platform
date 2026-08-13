"""Contract test for PATCH /organizations/current, GET .../members,
GET .../billing, GET /billing/plans (contracts/organizations-api.md,
contracts/billing-api.md, T079). Written before the endpoints exist —
MUST fail until T074/T075/T078 implement them."""

import uuid

import pytest


async def _signup_and_get_token(client, email="org-billing@example.com"):
    r = await client.post(
        "/auth/signup", json={"email": email, "password": "correct horse battery staple", "name": "Org Billing"}
    )
    return r.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_patch_current_organization_updates_name(client):
    token = await _signup_and_get_token(client)
    response = await client.patch(
        "/organizations/current", json={"name": "Renamed Org"}, headers=_auth_headers(token)
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Org"

    get_response = await client.get("/organizations/current", headers=_auth_headers(token))
    assert get_response.json()["name"] == "Renamed Org"


@pytest.mark.anyio
async def test_patch_current_organization_requires_authentication(client):
    response = await client.patch("/organizations/current", json={"name": "Nope"})
    assert response.status_code == 401


@pytest.mark.anyio
async def test_get_current_organization_members_shows_the_owner(client):
    token = await _signup_and_get_token(client)
    response = await client.get("/organizations/current/members", headers=_auth_headers(token))
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["role"] == "owner"
    assert items[0]["email"] == "org-billing@example.com"


@pytest.mark.anyio
async def test_get_billing_plans_lists_all_four_tiers(client):
    response = await client.get("/billing/plans")
    assert response.status_code == 200
    tiers = {item["tier"] for item in response.json()["items"]}
    assert tiers == {"free", "starter", "professional", "enterprise"}


@pytest.mark.anyio
async def test_get_current_billing_returns_free_plan_and_zero_usage(client):
    token = await _signup_and_get_token(client)
    response = await client.get("/organizations/current/billing", headers=_auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["plan"]["tier"] == "free"
    assert body["usage"]["test_executions"] == 0
    assert body["usage"]["ai_operations"] == 0
    assert "start" in body["period"]
    assert "end" in body["period"]


@pytest.mark.anyio
async def test_get_current_billing_requires_authentication(client):
    response = await client.get("/organizations/current/billing")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_create_invitation_is_not_implemented_yet(client):
    """T084: schema exists, route is a documented 501 stub (Future scope)."""
    token = await _signup_and_get_token(client)
    response = await client.post(
        "/organizations/current/invitations",
        json={"email": "new-member@example.com", "role": "member"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 501
    assert response.json()["error"]["code"] == "not_implemented"


@pytest.mark.anyio
async def test_remove_member_is_not_implemented_yet(client):
    """T084: schema exists, route is a documented 501 stub (Future scope)."""
    token = await _signup_and_get_token(client)

    response = await client.delete(f"/organizations/current/members/{uuid.uuid4()}", headers=_auth_headers(token))
    assert response.status_code == 501
    assert response.json()["error"]["code"] == "not_implemented"
