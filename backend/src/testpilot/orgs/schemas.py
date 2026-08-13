"""Request/response schemas for the Organizations API (contracts/organizations-api.md)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class OrganizationDetail(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan: str
    created_at: datetime


class UpdateOrganizationRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)


class MemberPublic(BaseModel):
    user_id: uuid.UUID
    name: str
    email: str
    role: str


class MembersListResponse(BaseModel):
    items: list[MemberPublic]


class CreateInvitationRequest(BaseModel):
    """Future scope (FR-016-FR-019) — the route accepting this body is a 501
    stub (T084) until the invite flow ships; the shape is fixed now per
    contracts/organizations-api.md so the eventual implementation is a
    drop-in, not a breaking API change."""

    email: str
    role: str
