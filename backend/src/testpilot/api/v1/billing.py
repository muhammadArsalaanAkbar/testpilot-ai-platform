"""Billing routes (contracts/billing-api.md)."""

import uuid

from fastapi import APIRouter, Depends

from testpilot.api.deps import CurrentUser, get_current_user
from testpilot.billing import service
from testpilot.billing.schemas import (
    BillingDetail,
    BillingPeriod,
    PlanLimits,
    PlanListItem,
    PlansListResponse,
    PlanSummary,
    UsageSummary,
)

router = APIRouter(tags=["billing"])


def _limits_from_plan(plan) -> PlanLimits:  # type: ignore[no-untyped-def]
    return PlanLimits(
        max_projects=plan.max_projects,
        max_test_executions_per_period=plan.max_test_executions_per_period,
        max_ai_operations_per_period=plan.max_ai_operations_per_period,
        max_members=plan.max_members,
    )


@router.get("/organizations/current/billing", response_model=BillingDetail)
async def get_current_billing(current_user: CurrentUser = Depends(get_current_user)) -> BillingDetail:
    plan, usage = await service.get_billing_summary(organization_id=uuid.UUID(current_user.organization_id))
    period_start, period_end = service.current_period()
    return BillingDetail(
        plan=PlanSummary(tier=plan.tier.value, limits=_limits_from_plan(plan)),
        usage=UsageSummary(**usage),
        period=BillingPeriod(start=period_start, end=period_end),
    )


@router.get("/billing/plans", response_model=PlansListResponse)
async def get_billing_plans() -> PlansListResponse:
    plans = await service.list_plans()
    return PlansListResponse(
        items=[
            PlanListItem(tier=plan.tier.value, limits=_limits_from_plan(plan), price_cents=plan.price_cents)
            for plan in plans
        ]
    )
