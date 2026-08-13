"""Billing/usage-limit business logic (FR-121-FR-127).

Two distinct enforcement shapes share the `usage_records` table
(billing/models.py's docstring explains why): `test_executions` and
`ai_operations` are period-accumulating consumption (checked and
incremented together, atomically, via `check_and_reserve_period_usage`);
`projects` and `members` are point-in-time resource counts, checked via
`check_count_limit` against a count the caller already computed (this
module has no dependency on the `projects`/`orgs` membership tables — the
caller, e.g. projects/service.py in a later phase, supplies the count it
just queried, keeping this library's own dependency graph unchanged
regardless of which future domain tables call into it).
"""

import datetime as dt
import uuid
from calendar import monthrange
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from testpilot.billing.models import UsageMetric, UsageRecord
from testpilot.core import cache
from testpilot.core.db import session_scope
from testpilot.core.exceptions import PlanLimitExceededError
from testpilot.orgs.models import Organization, SubscriptionPlan, SubscriptionTier

_PLAN_CACHE_NAMESPACE = "subscription_plan"

PeriodMetric = Literal["test_executions", "ai_operations"]
CountMetric = Literal["projects", "members"]

_METRIC_TO_PLAN_COLUMN: dict[str, str] = {
    "projects": "max_projects",
    "test_executions": "max_test_executions_per_period",
    "ai_operations": "max_ai_operations_per_period",
    "members": "max_members",
}


def current_period() -> tuple[dt.date, dt.date]:
    """MVP billing period = the current calendar month (UTC) — the spec
    does not pin a specific billing-cycle start date (no payment provider
    is wired at MVP, FR-127/INT-005), so calendar-month is a reasonable,
    simple default (constitution Simplicity principle)."""
    today = dt.datetime.now(dt.UTC).date()
    start = today.replace(day=1)
    end = today.replace(day=monthrange(today.year, today.month)[1])
    return start, end


async def _get_plan_for_organization(organization_id: uuid.UUID) -> SubscriptionPlan:
    """NFR-008: `subscription_plans` is shared catalog data (one row per
    tier, rarely written — only via the admin-only `set_plan_for_organization`
    below), so the plan row itself is cached, keyed by its own id
    (invalidated there on write) — resolving which plan an Organization is
    currently on still needs its own cheap single-row lookup by primary
    key every call, since that assignment is exactly what could have just
    changed."""
    async with session_scope(organization_id=str(organization_id)) as session:
        org_result = await session.execute(select(Organization).where(Organization.id == organization_id))
        organization = org_result.scalar_one()
        plan_id = organization.plan_id

    async def _load_plan() -> SubscriptionPlan | None:
        async with session_scope(organization_id=str(organization_id)) as session:
            plan_result = await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id))
            return plan_result.scalar_one_or_none()

    plan = await cache.get_or_set_model(
        namespace=_PLAN_CACHE_NAMESPACE, key=str(plan_id), model_cls=SubscriptionPlan, loader=_load_plan
    )
    assert plan is not None  # the plan a live Organization references always exists
    return plan


async def _get_or_create_usage_row(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    metric: UsageMetric,
    period_start: dt.date,
    period_end: dt.date,
) -> UsageRecord:
    result = await session.execute(
        select(UsageRecord).where(
            UsageRecord.organization_id == organization_id,
            UsageRecord.period_start == period_start,
            UsageRecord.metric == metric,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = UsageRecord(
            organization_id=organization_id,
            period_start=period_start,
            period_end=period_end,
            metric=metric,
            used_count=0,
        )
        session.add(row)
        await session.flush()
    return row


async def get_current_usage(*, organization_id: uuid.UUID) -> dict[str, int]:
    """Reads all four metrics for the current period, defaulting to 0 for
    any metric with no row yet (e.g. a brand-new Organization)."""
    period_start, period_end = current_period()
    async with session_scope(organization_id=str(organization_id)) as session:
        result = await session.execute(
            select(UsageRecord).where(
                UsageRecord.organization_id == organization_id,
                UsageRecord.period_start == period_start,
            )
        )
        rows = {row.metric: row.used_count for row in result.scalars()}
    return {metric.value: rows.get(metric, 0) for metric in UsageMetric}


async def check_and_reserve_period_usage(
    *, organization_id: uuid.UUID, metric: PeriodMetric, amount: int = 1
) -> None:
    """Atomically checks and increments a period-accumulating metric.
    Raises PlanLimitExceededError (naming the specific limit, FR-123)
    without incrementing if the limit would be exceeded."""
    plan = await _get_plan_for_organization(organization_id)
    limit = getattr(plan, _METRIC_TO_PLAN_COLUMN[metric])

    period_start, period_end = current_period()
    async with session_scope(organization_id=str(organization_id)) as session:
        row = await _get_or_create_usage_row(
            session,
            organization_id=organization_id,
            metric=UsageMetric(metric),
            period_start=period_start,
            period_end=period_end,
        )
        if limit is not None and row.used_count + amount > limit:
            raise PlanLimitExceededError(
                f"Organization has reached its {metric} limit for this billing period",
                limit=metric,
                used=row.used_count,
                max_allowed=limit,
            )
        row.used_count += amount
        session.add(row)


async def check_count_limit(*, organization_id: uuid.UUID, metric: CountMetric, prospective_count: int) -> None:
    """Raises PlanLimitExceededError if `prospective_count` (the count the
    caller computed for the action it's about to take, e.g. "projects that
    would exist after this create") would exceed the plan limit. Does not
    itself persist anything — callers that want the usage_records snapshot
    kept current should also call `set_count_usage` after their action
    succeeds; that is a display/reporting concern, not an enforcement one."""
    plan = await _get_plan_for_organization(organization_id)
    limit = getattr(plan, _METRIC_TO_PLAN_COLUMN[metric])
    if limit is not None and prospective_count > limit:
        raise PlanLimitExceededError(
            f"Organization has reached its {metric} limit",
            limit=metric,
            used=prospective_count - 1,
            max_allowed=limit,
        )


async def set_count_usage(*, organization_id: uuid.UUID, metric: CountMetric, count: int) -> None:
    """Upserts the current live count for a point-in-time metric into the
    current period's usage_records row, so GET .../billing can display it
    without recomputing a live COUNT(*) against another domain's table."""
    period_start, period_end = current_period()
    async with session_scope(organization_id=str(organization_id)) as session:
        row = await _get_or_create_usage_row(
            session,
            organization_id=organization_id,
            metric=UsageMetric(metric),
            period_start=period_start,
            period_end=period_end,
        )
        row.used_count = count
        session.add(row)


async def get_billing_summary(*, organization_id: uuid.UUID) -> tuple[SubscriptionPlan, dict[str, int]]:
    plan = await _get_plan_for_organization(organization_id)
    usage = await get_current_usage(organization_id=organization_id)
    return plan, usage


async def list_plans() -> list[SubscriptionPlan]:
    """Public (contracts/billing-api.md) — no Organization scoping needed;
    subscription_plans is reference/catalog data (data-model.md), not
    tenant data."""
    async with session_scope() as session:
        result = await session.execute(select(SubscriptionPlan))
        return list(result.scalars().all())


async def set_plan_for_organization(
    *,
    organization_id: uuid.UUID,
    tier: SubscriptionTier,
    max_projects: int | None = None,
    max_test_executions_per_period: int | None = None,
    max_ai_operations_per_period: int | None = None,
    max_members: int | None = None,
) -> tuple[Organization, SubscriptionPlan]:
    """testpilot-cli billing set-plan (quickstart.md Section 13, FR-125).

    Admin/test-only tool: assigns the Organization to `tier`'s plan row,
    optionally overriding that tier's limits in place. `subscription_plans`
    is shared catalog data (one row per tier, not per Organization), so an
    override here affects every Organization on that tier — acceptable for
    this local/admin CLI's purpose (deliberately triggering plan-limit
    errors for testing), not exposed via the authenticated HTTP API.
    """
    async with session_scope() as session:
        plan_result = await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.tier == tier))
        plan = plan_result.scalar_one()
        if max_projects is not None:
            plan.max_projects = max_projects
        if max_test_executions_per_period is not None:
            plan.max_test_executions_per_period = max_test_executions_per_period
        if max_ai_operations_per_period is not None:
            plan.max_ai_operations_per_period = max_ai_operations_per_period
        if max_members is not None:
            plan.max_members = max_members
        session.add(plan)

        org_result = await session.execute(select(Organization).where(Organization.id == organization_id))
        organization = org_result.scalar_one()
        organization.plan_id = plan.id
        session.add(organization)

        await session.flush()
        await session.refresh(plan)
        await session.refresh(organization)
        plan_id = plan.id

    # Every Organization on this tier shares this one plan row (and thus
    # this one cache entry, keyed by plan.id) — invalidating here, after
    # commit, covers all of them, not just `organization_id`.
    await cache.invalidate(namespace=_PLAN_CACHE_NAMESPACE, key=str(plan_id))
    return organization, plan
