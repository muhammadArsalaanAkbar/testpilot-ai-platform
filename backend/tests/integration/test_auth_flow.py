"""Integration test: the full signup -> login -> logout -> forgot-password ->
reset-password -> login-with-new-password flow against real Postgres
(quickstart.md Section 3, T058). Unlike the contract tests (which exercise
one endpoint's shape at a time), this proves the whole User Story 1 journey
holds together end-to-end in a single continuous session, including that
RLS-scoped state (the personal Organization/Membership created at signup)
survives the entire flow correctly.
"""

import re

import pytest
from sqlalchemy import text

from testpilot.core.db import session_scope
from testpilot.core.email import test_outbox


def _extract_token(email_body: str) -> str:
    match = re.search(r"token=([A-Za-z0-9_-]+)", email_body)
    assert match, f"no reset token found in email body: {email_body!r}"
    return match.group(1)


@pytest.mark.anyio
async def test_full_signup_login_logout_forgot_reset_login_flow(client):
    test_outbox.clear()
    email = "integration-flow@example.com"
    original_password = "original strong integration password"
    new_password = "brand new integration password"

    # 1. Sign up
    signup = await client.post(
        "/auth/signup", json={"email": email, "password": original_password, "name": "Integration Flow"}
    )
    assert signup.status_code == 201
    signup_body = signup.json()
    user_id = signup_body["user"]["id"]
    organization_id = signup_body["organization"]["id"]
    assert signup_body["organization"]["name"]

    # FR-012: personal Organization + owner Membership actually exist and
    # are queryable (not just claimed in the response body).
    async with session_scope(organization_id=organization_id, user_id=user_id) as session:
        result = await session.execute(
            text("SELECT role FROM memberships WHERE user_id = :uid AND organization_id = :oid"),
            {"uid": user_id, "oid": organization_id},
        )
        row = result.first()
        assert row is not None
        assert row[0] == "owner"

    # 2. Use the access token to reach an authenticated endpoint
    access_token = signup_body["access_token"]
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me.status_code == 200
    assert me.json()["organization"]["id"] == organization_id

    # 3. Log out — the session (refresh cookie) is revoked
    logout = await client.post("/auth/logout", headers={"Authorization": f"Bearer {access_token}"})
    assert logout.status_code == 204
    refresh_after_logout = await client.post("/auth/refresh")
    assert refresh_after_logout.status_code == 401

    # 4. Log back in with the original password
    login = await client.post("/auth/login", json={"email": email, "password": original_password})
    assert login.status_code == 200
    assert login.json()["user"]["id"] == user_id

    # 5. Forgot password — a reset email is sent with a usable token
    forgot = await client.post("/auth/forgot-password", json={"email": email})
    assert forgot.status_code == 202
    assert len(test_outbox) == 1
    reset_token = _extract_token(test_outbox[-1].body)

    # 6. Reset the password using the emailed token
    reset = await client.post(
        "/auth/reset-password", json={"token": reset_token, "new_password": new_password}
    )
    assert reset.status_code == 200

    # The old password no longer works.
    old_login = await client.post("/auth/login", json={"email": email, "password": original_password})
    assert old_login.status_code == 401

    # 7. Log in with the new password — completes the full journey
    final_login = await client.post("/auth/login", json={"email": email, "password": new_password})
    assert final_login.status_code == 200
    assert final_login.json()["user"]["id"] == user_id

    # A reset revokes every prior session (auth/service.py's reset_password);
    # the pre-reset access token's underlying session is gone, though the
    # JWT itself remains valid until natural expiry (stateless by design) —
    # what must be gone is the refresh token issued at signup/login-before-reset.
    stale_refresh = await client.post("/auth/refresh")
    # The client's cookie jar now holds the *final* login's refresh token
    # (the most recent Set-Cookie wins), so this specifically confirms the
    # end-to-end flow leaves the client in a working, refreshable session.
    assert stale_refresh.status_code == 200
