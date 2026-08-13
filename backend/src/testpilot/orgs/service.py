"""Organizations business logic (contracts/organizations-api.md, FR-012-FR-019)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from testpilot.auth.models import User
from testpilot.core.db import session_scope
from testpilot.core.exceptions import InsufficientRoleError
from testpilot.orgs.models import Membership, MembershipRole, Organization, SubscriptionPlan

_WRITE_ROLES = {MembershipRole.owner, MembershipRole.admin}


async def get_current_organization(*, organization_id: uuid.UUID) -> tuple[Organization, SubscriptionPlan]:
    """`organization_id` MUST come only from the authenticated user's own
    session claims (never a client-supplied path/query parameter) —
    `organizations` has no RLS policy of its own (data-model.md: it *is*
    the tenant scope, not scoped by one), so this function is the only
    guard against reading another Organization's row."""
    async with session_scope(organization_id=str(organization_id)) as session:
        org_result = await session.execute(select(Organization).where(Organization.id == organization_id))
        organization = org_result.scalar_one()

        plan_result = await session.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == organization.plan_id)
        )
        plan = plan_result.scalar_one()

        return organization, plan


async def _get_membership(
    session: AsyncSession, *, organization_id: uuid.UUID, user_id: uuid.UUID
) -> Membership:
    result = await session.execute(
        select(Membership).where(Membership.organization_id == organization_id, Membership.user_id == user_id)
    )
    return result.scalar_one()


async def update_organization(*, organization_id: uuid.UUID, user_id: uuid.UUID, name: str | None) -> Organization:
    """FR-013. Authorization note (contracts/organizations-api.md): owner/
    admin only — enforced here server-side, not just hidden client-side
    (SEC-003)."""
    async with session_scope(organization_id=str(organization_id), user_id=str(user_id)) as session:
        membership = await _get_membership(session, organization_id=organization_id, user_id=user_id)
        if membership.role not in _WRITE_ROLES:
            raise InsufficientRoleError("Only the Organization owner or an admin can update its settings")

        org_result = await session.execute(select(Organization).where(Organization.id == organization_id))
        organization = org_result.scalar_one()
        if name is not None:
            organization.name = name
        session.add(organization)
        await session.flush()
        await session.refresh(organization)
        return organization


async def list_members(*, organization_id: uuid.UUID, user_id: uuid.UUID) -> list[tuple[Membership, User]]:
    """FR-015. MVP always returns exactly one row (the signed-up owner) —
    the query itself already supports multiple members for when the Future
    invite flow (FR-016-FR-019) ships."""
    async with session_scope(organization_id=str(organization_id), user_id=str(user_id)) as session:
        result = await session.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.organization_id == organization_id)
        )
        return list(result.all())
