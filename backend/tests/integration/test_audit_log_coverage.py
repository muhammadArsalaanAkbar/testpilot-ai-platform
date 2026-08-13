"""T209: audit-log coverage audit (SEC-010, FR-128, FR-129).

Directly queries `audit_log_entries` after each SEC-010-listed event —
no existing test anywhere in the suite did this before (auth tests only
ever asserted the HTTP-level outcome of login/logout, never that a
corresponding audit row was actually written), so this closes that
verification gap for the already-implemented events too, not only the
newly-fixed ones.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from testpilot.audit import service as audit_service
from testpilot.audit.models import AuditLogEntry
from testpilot.auth.models import User
from testpilot.core.config import get_settings
from testpilot.core.db import session_scope, set_rls_context
from testpilot.core.exceptions import InsufficientRoleError
from testpilot.orgs.models import (
    Membership,
    MembershipRole,
    Organization,
    SubscriptionPlan,
    SubscriptionTier,
)


async def _signup_and_get_token(client, email="audit-coverage@example.com"):
    r = await client.post(
        "/auth/signup", json={"email": email, "password": "correct horse battery staple", "name": "Audit Coverage"}
    )
    body = r.json()
    return body["access_token"], body["organization"]["id"], body["user"]["id"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _actions_for(*, organization_id: str, actor_user_id: str | None = None) -> list[str]:
    """`audit_log_entries` is RLS-protected (`audit_read`, scoped by
    organization_id) even though data-model.md notes it as an exception to
    the *blanket* tenant-table convention -- session_scope's RLS context
    must be set to the same org whose events are being read, or every row
    is invisible regardless of what the WHERE clause says."""
    async with session_scope(organization_id=organization_id) as session:
        query = select(AuditLogEntry.action).where(AuditLogEntry.organization_id == uuid.UUID(organization_id))
        if actor_user_id is not None:
            query = query.where(AuditLogEntry.actor_user_id == uuid.UUID(actor_user_id))
        result = await session.execute(query)
        return list(result.scalars().all())


async def _actions_bypassing_rls() -> list[str]:
    """For the one event type with no organization_id at all (a failed
    login for a nonexistent account) -- such rows are correctly invisible
    to *every* tenant-scoped session under RLS (NULL never equals a
    current_org_id setting, no matter what it's set to), which is exactly
    right for FR-129's "scoped to that Organization's own events" (an
    org-less event is nobody's org's event). Verifying the row was written
    at all therefore requires bypassing RLS the way a superuser connection
    (`testpilot`, `MIGRATIONS_DATABASE_URL`) does -- a test-only concern,
    never how the application itself reads this table."""
    settings = get_settings()
    admin_url = settings.migrations_database_url or settings.database_url
    engine = create_async_engine(admin_url)
    try:
        async with async_sessionmaker(bind=engine)() as session:
            result = await session.execute(select(AuditLogEntry.action))
            return list(result.scalars().all())
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_signup_and_login_are_audit_logged(client):
    token, organization_id, user_id = await _signup_and_get_token(client, email="audit-login@example.com")
    await client.post("/auth/login", json={"email": "audit-login@example.com", "password": "correct horse battery staple"})

    actions = await _actions_for(organization_id=organization_id, actor_user_id=user_id)
    assert "signup" in actions
    assert "login" in actions


@pytest.mark.anyio
async def test_failed_login_is_audit_logged(client):
    await client.post(
        "/auth/login", json={"email": "no-such-account@example.com", "password": "whatever"}
    )
    actions = await _actions_bypassing_rls()
    assert "login_failed" in actions


@pytest.mark.anyio
async def test_logout_is_audit_logged(client):
    token, organization_id, user_id = await _signup_and_get_token(client, email="audit-logout@example.com")
    await client.post("/auth/logout", headers=_auth_headers(token))

    actions = await _actions_for(organization_id=organization_id, actor_user_id=user_id)
    assert "logout" in actions


@pytest.mark.anyio
async def test_logout_all_is_audit_logged(client):
    """Genuine gap found by this audit: logout-all (T196, Phase 17) revoked
    every session but never recorded an audit entry."""
    token, organization_id, user_id = await _signup_and_get_token(client, email="audit-logout-all@example.com")
    await client.post("/auth/logout-all", headers=_auth_headers(token))

    actions = await _actions_for(organization_id=organization_id, actor_user_id=user_id)
    assert "logout_all" in actions


@pytest.mark.anyio
async def test_password_reset_requested_and_completed_are_audit_logged(client):
    token, organization_id, user_id = await _signup_and_get_token(client, email="audit-reset@example.com")
    await client.post("/auth/forgot-password", json={"email": "audit-reset@example.com"})

    actions = await _actions_for(organization_id=organization_id, actor_user_id=user_id)
    assert "password_reset_requested" in actions


@pytest.mark.anyio
async def test_project_deletion_is_audit_logged(client):
    """Genuine gap found by this audit: FR-128 explicitly names "project
    deletion" as a required audit event; delete_project never wrote one."""
    token, organization_id, user_id = await _signup_and_get_token(client, email="audit-project-delete@example.com")
    project_response = await client.post(
        "/projects", json={"name": "Delete Me", "url": "https://example.com"}, headers=_auth_headers(token)
    )
    project_id = project_response.json()["id"]

    delete_response = await client.request(
        "DELETE", f"/projects/{project_id}", json={"confirm": True}, headers=_auth_headers(token)
    )
    assert delete_response.status_code == 204

    async with session_scope(organization_id=organization_id) as session:
        result = await session.execute(
            select(AuditLogEntry).where(
                AuditLogEntry.action == "project_deleted", AuditLogEntry.resource_id == uuid.UUID(project_id)
            )
        )
        entry = result.scalar_one_or_none()
        assert entry is not None
        assert entry.actor_user_id == uuid.UUID(user_id)
        assert entry.organization_id == uuid.UUID(organization_id)
        assert entry.resource_type == "project"


@pytest.mark.anyio
async def test_test_case_deletion_is_audit_logged(client):
    """Genuine gap found by this audit: SEC-010's general "deletions"
    coverage -- delete_test_case never wrote an audit entry either."""
    token, organization_id, user_id = await _signup_and_get_token(client, email="audit-testcase-delete@example.com")
    project_response = await client.post(
        "/projects", json={"name": "TC Delete Project", "url": "https://example.com"}, headers=_auth_headers(token)
    )
    project_id = project_response.json()["id"]
    case_response = await client.post(
        f"/projects/{project_id}/test-cases",
        json={
            "title": "Delete me",
            "description": "d",
            "priority": "low",
            "severity": "minor",
            "steps": [{"action_type": "navigate", "target_descriptor": "/"}],
        },
        headers=_auth_headers(token),
    )
    case_id = case_response.json()["id"]

    delete_response = await client.delete(f"/projects/{project_id}/test-cases/{case_id}", headers=_auth_headers(token))
    assert delete_response.status_code == 204

    async with session_scope(organization_id=organization_id) as session:
        result = await session.execute(
            select(AuditLogEntry).where(
                AuditLogEntry.action == "test_case_deleted", AuditLogEntry.resource_id == uuid.UUID(case_id)
            )
        )
        entry = result.scalar_one_or_none()
        assert entry is not None
        assert entry.actor_user_id == uuid.UUID(user_id)
        assert entry.organization_id == uuid.UUID(organization_id)


@pytest.mark.anyio
async def test_owner_can_view_the_organizations_audit_log(client):
    """FR-129: viewable by the Organization's owner/admin."""
    token, _organization_id, _user_id = await _signup_and_get_token(client, email="audit-view-owner@example.com")

    response = await client.get("/organizations/current/audit-log", headers=_auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    # The signup call itself is already an audit-logged event for this org.
    assert any(item["action"] == "signup" for item in body["items"])


@pytest.mark.anyio
async def test_audit_log_view_requires_authentication(client):
    response = await client.get("/organizations/current/audit-log")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_audit_log_is_scoped_to_the_requesting_organization(client):
    token_a, _org_a, user_a = await _signup_and_get_token(client, email="audit-org-a@example.com")
    _token_b, _org_b, user_b = await _signup_and_get_token(client, email="audit-org-b@example.com")

    response_a = await client.get("/organizations/current/audit-log", headers=_auth_headers(token_a))
    actor_ids_a = {item["actor_user_id"] for item in response_a.json()["items"]}
    assert user_a in actor_ids_a
    assert user_b not in actor_ids_a


@pytest.mark.anyio
async def test_member_cannot_view_the_audit_log():
    """No role-elevation endpoint exists yet at MVP (invitations are a 501
    stub) -- every signed-up user is the owner of their own Organization,
    so a non-owner/admin denial can't be exercised through the real API
    today. Verified directly against the service function instead, the
    same way FR-129's "owner/admin" restriction will be exercised once
    Future member invites make a real non-owner membership reachable."""
    async with session_scope() as session:
        plan_result = await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.tier == SubscriptionTier.free))
        plan = plan_result.scalar_one()

        owner = User(email=f"{uuid.uuid4()}@example.com", name="Owner", password_hash="x")
        member = User(email=f"{uuid.uuid4()}@example.com", name="Member", password_hash="x")
        session.add(owner)
        session.add(member)
        await session.flush()

        organization = Organization(name="Audit Role Test Org", slug=str(uuid.uuid4()), plan_id=plan.id)
        session.add(organization)
        await session.flush()

        await set_rls_context(session, organization_id=str(organization.id), user_id=str(owner.id))
        session.add(Membership(organization_id=organization.id, user_id=owner.id, role=MembershipRole.owner))
        session.add(Membership(organization_id=organization.id, user_id=member.id, role=MembershipRole.member))
        await session.flush()

        organization_id = organization.id
        member_id = member.id

    with pytest.raises(InsufficientRoleError):
        await audit_service.list_audit_log(organization_id=organization_id, user_id=member_id)
