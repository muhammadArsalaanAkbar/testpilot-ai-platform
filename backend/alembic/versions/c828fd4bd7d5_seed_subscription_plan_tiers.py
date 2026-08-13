"""seed subscription plan tiers

Revision ID: c828fd4bd7d5
Revises: 0e1c705a31ba
Create Date: 2026-08-10 11:32:53.697448

Seeds the four MVP-required plan tiers (FR-120) with placeholder limits and
prices — the spec intentionally does not pin exact numeric limits (an
implementation/config decision, per spec.md's Assumptions), so these are a
reasonable, documented starting point that can be tuned via
`backend/scripts/seed_reference_data.py` (Phase 19) without a schema change.
`null` means unlimited (data-model.md).
"""
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c828fd4bd7d5"
down_revision: str | Sequence[str] | None = "0e1c705a31ba"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TIER_ENUM = sa.Enum(
    "free", "starter", "professional", "enterprise", name="subscriptiontier", create_type=False
)

_TABLE = sa.table(
    "subscription_plans",
    sa.column("id", sa.Uuid),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
    sa.column("tier", _TIER_ENUM),
    sa.column("max_projects", sa.Integer),
    sa.column("max_test_executions_per_period", sa.Integer),
    sa.column("max_ai_operations_per_period", sa.Integer),
    sa.column("max_members", sa.Integer),
    sa.column("price_cents", sa.Integer),
)

_PLANS = [
    {
        "tier": "free",
        "max_projects": 1,
        "max_test_executions_per_period": 50,
        "max_ai_operations_per_period": 20,
        "max_members": 1,
        "price_cents": 0,
    },
    {
        "tier": "starter",
        "max_projects": 5,
        "max_test_executions_per_period": 500,
        "max_ai_operations_per_period": 200,
        "max_members": 3,
        "price_cents": 2900,
    },
    {
        "tier": "professional",
        "max_projects": 25,
        "max_test_executions_per_period": 5000,
        "max_ai_operations_per_period": 2000,
        "max_members": 10,
        "price_cents": 9900,
    },
    {
        "tier": "enterprise",
        "max_projects": None,
        "max_test_executions_per_period": None,
        "max_ai_operations_per_period": None,
        "max_members": None,
        "price_cents": None,
    },
]


def upgrade() -> None:
    now = datetime.now(UTC)
    op.bulk_insert(
        _TABLE,
        [{"id": uuid.uuid4(), "created_at": now, "updated_at": now, **plan} for plan in _PLANS],
    )


def downgrade() -> None:
    op.execute(
        f"DELETE FROM subscription_plans WHERE tier IN "
        f"({', '.join(repr(p['tier']) for p in _PLANS)})"
    )
