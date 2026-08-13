"""Audit log writes and reads (SEC-010, FR-128, FR-129). Writes: every call
opens its own transaction, independent of the auth operation it's logging —
a failed login, for example, rolls back its own (empty) business
transaction, but the `login_failed` audit entry must still persist. Reads
(T209): Organization-scoped, owner/admin only.
"""

import uuid
from typing import Any

from sqlalchemy import func, select

from testpilot.audit.models import AuditLogEntry
from testpilot.core.db import session_scope
from testpilot.core.exceptions import InsufficientRoleError
from testpilot.orgs.models import Membership, MembershipRole

_READ_ROLES = {MembershipRole.owner, MembershipRole.admin}


async def record(
    *,
    action: str,
    actor_user_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    async with session_scope() as session:
        session.add(
            AuditLogEntry(
                action=action,
                actor_user_id=actor_user_id,
                organization_id=organization_id,
                resource_type=resource_type,
                resource_id=resource_id,
                event_metadata=metadata or {},
            )
        )


async def list_audit_log(
    *, organization_id: uuid.UUID, user_id: uuid.UUID, page: int = 1, page_size: int = 25
) -> tuple[list[AuditLogEntry], int]:
    """FR-129: viewable by the Organization's owner/admin, strictly scoped
    to that Organization's own events — enforced both by this role check
    and, independently, by audit_log_entries' own RLS policy (defense in
    depth, SEC-011)."""
    async with session_scope(organization_id=str(organization_id), user_id=str(user_id)) as session:
        membership_result = await session.execute(
            select(Membership).where(Membership.organization_id == organization_id, Membership.user_id == user_id)
        )
        membership = membership_result.scalar_one()
        if membership.role not in _READ_ROLES:
            raise InsufficientRoleError("Only the Organization owner or an admin can view the audit log")

        total_result = await session.execute(
            select(func.count()).select_from(AuditLogEntry).where(AuditLogEntry.organization_id == organization_id)
        )
        total = total_result.scalar_one()

        result = await session.execute(
            select(AuditLogEntry)
            .where(AuditLogEntry.organization_id == organization_id)
            .order_by(AuditLogEntry.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total
