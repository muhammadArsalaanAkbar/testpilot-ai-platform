"""Idempotent reference-data seed script (T205, FR-119-FR-121).

Ensures the four MVP subscription plan tiers exist with their currently
configured limits — safe to re-run against any environment (a fresh
deploy, or to push a tuned limit without a schema migration). The initial
migration (`c828fd4bd7d5_seed_subscription_plan_tiers.py`) seeds these same
rows once, at migration time, for a brand-new database; this script is the
separate, repeatable path for updating them afterward, per that
migration's own docstring — deliberately NOT a migration itself, since a
migration only ever runs once per database and reference-data values (unlike
schema) are the kind of thing that legitimately needs tuning later.

Usage: python scripts/seed_reference_data.py
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from testpilot.core.db import session_scope
from testpilot.orgs.models import SubscriptionPlan, SubscriptionTier

PLANS: dict[SubscriptionTier, dict[str, int | None]] = {
    SubscriptionTier.free: {
        "max_projects": 1,
        "max_test_executions_per_period": 50,
        "max_ai_operations_per_period": 20,
        "max_members": 1,
        "price_cents": 0,
    },
    SubscriptionTier.starter: {
        "max_projects": 5,
        "max_test_executions_per_period": 500,
        "max_ai_operations_per_period": 200,
        "max_members": 3,
        "price_cents": 2900,
    },
    SubscriptionTier.professional: {
        "max_projects": 25,
        "max_test_executions_per_period": 5000,
        "max_ai_operations_per_period": 2000,
        "max_members": 10,
        "price_cents": 9900,
    },
    SubscriptionTier.enterprise: {
        "max_projects": None,
        "max_test_executions_per_period": None,
        "max_ai_operations_per_period": None,
        "max_members": None,
        "price_cents": None,
    },
}


async def seed_reference_data() -> list[str]:
    """Upserts every tier in `PLANS`. Returns one summary line per tier
    ("created"/"updated"/"unchanged") for the caller to report."""
    summary = []
    async with session_scope() as session:
        for tier, limits in PLANS.items():
            result = await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.tier == tier))
            plan = result.scalar_one_or_none()

            if plan is None:
                session.add(SubscriptionPlan(tier=tier, **limits))
                summary.append(f"created {tier.value}")
                continue

            changed = any(getattr(plan, field) != value for field, value in limits.items())
            if not changed:
                summary.append(f"unchanged {tier.value}")
                continue

            for field, value in limits.items():
                setattr(plan, field, value)
            session.add(plan)
            summary.append(f"updated {tier.value}")

    return summary


def main() -> int:
    summary = asyncio.run(seed_reference_data())
    for line in summary:
        print(line)
    print(f"Reference data seed complete ({len(summary)} plan tier(s) checked).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
