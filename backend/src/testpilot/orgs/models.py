import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import UniqueConstraint
from sqlmodel import Field

from testpilot.core.models import BaseTable, TenantTable, tz_datetime_field


class MembershipRole(StrEnum):
    owner = "owner"
    admin = "admin"
    member = "member"


class SubscriptionTier(StrEnum):
    free = "free"
    starter = "starter"
    professional = "professional"
    enterprise = "enterprise"


class SubscriptionPlan(BaseTable, table=True):
    """Reference/catalog table — not Organization-scoped, no RLS (data-model.md)."""

    __tablename__ = "subscription_plans"

    tier: SubscriptionTier = Field(sa_column_kwargs={"unique": True}, nullable=False)
    max_projects: int | None = None
    max_test_executions_per_period: int | None = None
    max_ai_operations_per_period: int | None = None
    max_members: int | None = None
    price_cents: int | None = None


class Organization(BaseTable, table=True):
    """The tenant root. Not itself organization_id-scoped — it *is* the scope."""

    __tablename__ = "organizations"

    name: str = Field(nullable=False)
    slug: str = Field(sa_column_kwargs={"unique": True}, nullable=False)
    plan_id: uuid.UUID = Field(foreign_key="subscription_plans.id", nullable=False)


class Membership(BaseTable, table=True):
    """Join of User and Organization with a Role.

    MVP always produces exactly one Owner membership per Organization at
    signup (FR-012); the role enum and this table already support
    admin/member for the Future invite flow (FR-016-FR-019) without a
    schema change later.
    """

    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),)

    organization_id: uuid.UUID = Field(foreign_key="organizations.id", nullable=False, index=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False, index=True)
    role: MembershipRole = Field(default=MembershipRole.owner, nullable=False)


class Invitation(TenantTable, table=True):
    """Future scope (FR-016-FR-019, data-model.md) — schema only at MVP; the
    POST .../invitations and DELETE .../members/{user_id} routes that would
    write/read this table are 501 stubs (T084) until the invite flow ships.
    """

    __tablename__ = "invitations"

    email: str = Field(nullable=False)
    role: MembershipRole = Field(nullable=False)
    invited_by_user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False)
    token_hash: str = Field(nullable=False)
    expires_at: datetime = tz_datetime_field(nullable=False)
    accepted_at: datetime | None = tz_datetime_field(nullable=True)
