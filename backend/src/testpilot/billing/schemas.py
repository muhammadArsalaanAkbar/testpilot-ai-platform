"""Request/response schemas for the Billing API (contracts/billing-api.md)."""

import datetime as dt

from pydantic import BaseModel


class PlanLimits(BaseModel):
    max_projects: int | None
    max_test_executions_per_period: int | None
    max_ai_operations_per_period: int | None
    max_members: int | None


class PlanSummary(BaseModel):
    tier: str
    limits: PlanLimits


class PlanListItem(BaseModel):
    tier: str
    limits: PlanLimits
    price_cents: int | None


class PlansListResponse(BaseModel):
    items: list[PlanListItem]


class UsageSummary(BaseModel):
    projects: int
    test_executions: int
    ai_operations: int
    members: int


class BillingPeriod(BaseModel):
    start: dt.date
    end: dt.date


class BillingDetail(BaseModel):
    plan: PlanSummary
    usage: UsageSummary
    period: BillingPeriod
