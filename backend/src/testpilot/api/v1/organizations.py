"""Organizations routes (contracts/organizations-api.md)."""

import uuid

from fastapi import APIRouter, Depends

from testpilot.api.deps import CurrentUser, get_current_user
from testpilot.api.pagination import PaginationParams
from testpilot.audit import service as audit_service
from testpilot.audit.schemas import AuditLogEntryPublic, AuditLogListResponse
from testpilot.core.exceptions import NotImplementedYetError
from testpilot.orgs import service
from testpilot.orgs.schemas import (
    CreateInvitationRequest,
    MemberPublic,
    MembersListResponse,
    OrganizationDetail,
    UpdateOrganizationRequest,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("/current", response_model=OrganizationDetail)
async def get_current_organization(current_user: CurrentUser = Depends(get_current_user)) -> OrganizationDetail:
    organization, plan = await service.get_current_organization(
        organization_id=uuid.UUID(current_user.organization_id)
    )
    return OrganizationDetail(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        plan=plan.tier.value,
        created_at=organization.created_at,
    )


@router.patch("/current", response_model=OrganizationDetail)
async def update_current_organization(
    payload: UpdateOrganizationRequest, current_user: CurrentUser = Depends(get_current_user)
) -> OrganizationDetail:
    organization = await service.update_organization(
        organization_id=uuid.UUID(current_user.organization_id),
        user_id=uuid.UUID(current_user.user_id),
        name=payload.name,
    )
    _org, plan = await service.get_current_organization(organization_id=organization.id)
    return OrganizationDetail(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        plan=plan.tier.value,
        created_at=organization.created_at,
    )


@router.get("/current/members", response_model=MembersListResponse)
async def list_current_organization_members(
    current_user: CurrentUser = Depends(get_current_user),
) -> MembersListResponse:
    rows = await service.list_members(
        organization_id=uuid.UUID(current_user.organization_id), user_id=uuid.UUID(current_user.user_id)
    )
    return MembersListResponse(
        items=[
            MemberPublic(user_id=user.id, name=user.name, email=user.email, role=membership.role.value)
            for membership, user in rows
        ]
    )


@router.get("/current/audit-log", response_model=AuditLogListResponse)
async def list_current_organization_audit_log(
    pagination: PaginationParams = Depends(),
    current_user: CurrentUser = Depends(get_current_user),
) -> AuditLogListResponse:
    """FR-129: owner/admin only, scoped strictly to this Organization's own events."""
    entries, total = await audit_service.list_audit_log(
        organization_id=uuid.UUID(current_user.organization_id),
        user_id=uuid.UUID(current_user.user_id),
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return AuditLogListResponse(
        items=[
            AuditLogEntryPublic(
                id=entry.id,
                action=entry.action,
                actor_user_id=entry.actor_user_id,
                resource_type=entry.resource_type,
                resource_id=entry.resource_id,
                event_metadata=entry.event_metadata,
                created_at=entry.created_at,
            )
            for entry in entries
        ],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )


@router.post("/current/invitations", status_code=501)
async def create_invitation(
    payload: CreateInvitationRequest, current_user: CurrentUser = Depends(get_current_user)
) -> None:
    """Future scope (FR-016-FR-019, contracts/organizations-api.md) — the
    `invitations` table (T084) exists so this becomes a drop-in later, but
    nothing writes to it yet."""
    raise NotImplementedYetError("Inviting members is not available yet")


@router.delete("/current/members/{user_id}", status_code=501)
async def remove_member(user_id: uuid.UUID, current_user: CurrentUser = Depends(get_current_user)) -> None:
    """Future scope (FR-018, contracts/organizations-api.md)."""
    raise NotImplementedYetError("Removing members is not available yet")
