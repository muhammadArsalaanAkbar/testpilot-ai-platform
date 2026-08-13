"""T205: the reference-data seed script is idempotent and self-healing —
running it against an already-seeded database changes nothing, running it
after a value has drifted corrects it, and running it after a tier row was
deleted entirely re-creates it.
"""

import sys
from pathlib import Path

import pytest
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from seed_reference_data import PLANS, seed_reference_data  # noqa: E402

from testpilot.core.db import session_scope
from testpilot.orgs.models import SubscriptionPlan, SubscriptionTier


@pytest.mark.anyio
async def test_seeding_an_already_seeded_database_reports_everything_unchanged():
    # The migration already seeded these four rows for every test's fresh
    # schema (this test DB was migrated to head, same as any environment).
    first_pass = await seed_reference_data()
    assert all(line.startswith("unchanged ") for line in first_pass)
    assert len(first_pass) == len(PLANS)


@pytest.mark.anyio
async def test_seeding_corrects_a_drifted_value():
    async with session_scope() as session:
        result = await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.tier == SubscriptionTier.free))
        free_plan = result.scalar_one()
        original_max_projects = free_plan.max_projects
        free_plan.max_projects = 999
        session.add(free_plan)

    try:
        summary = await seed_reference_data()
        assert "updated free" in summary

        async with session_scope() as session:
            result = await session.execute(
                select(SubscriptionPlan).where(SubscriptionPlan.tier == SubscriptionTier.free)
            )
            corrected = result.scalar_one()
            assert corrected.max_projects == PLANS[SubscriptionTier.free]["max_projects"]
    finally:
        async with session_scope() as session:
            result = await session.execute(
                select(SubscriptionPlan).where(SubscriptionPlan.tier == SubscriptionTier.free)
            )
            plan = result.scalar_one()
            plan.max_projects = original_max_projects
            session.add(plan)


@pytest.mark.anyio
async def test_seeding_recreates_a_deleted_tier():
    async with session_scope() as session:
        result = await session.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.tier == SubscriptionTier.enterprise)
        )
        enterprise_plan = result.scalar_one()
        await session.delete(enterprise_plan)

    try:
        summary = await seed_reference_data()
        assert "created enterprise" in summary

        async with session_scope() as session:
            result = await session.execute(
                select(SubscriptionPlan).where(SubscriptionPlan.tier == SubscriptionTier.enterprise)
            )
            assert result.scalar_one_or_none() is not None
    finally:
        # Leave the DB in the same "seeded" state every other test assumes.
        await seed_reference_data()
