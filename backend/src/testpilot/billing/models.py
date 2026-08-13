import datetime as dt
from enum import StrEnum

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field

from testpilot.core.models import TenantTable


class UsageMetric(StrEnum):
    projects = "projects"
    test_executions = "test_executions"
    ai_operations = "ai_operations"
    members = "members"


class UsageRecord(TenantTable, table=True):
    """Tracked consumption/count against a Subscription's limits, per
    Organization, per billing period, per metric (data-model.md).

    Two different semantics share this one table by design (billing/
    service.py is what enforces the distinction, not the schema):
    `test_executions`/`ai_operations` are period-accumulating consumption
    (used_count is incremented); `projects`/`members` are point-in-time
    resource counts (used_count is set to the current live count, not
    incremented) — kept in the same table so GET .../billing can read all
    four metrics for "the current period" with one uniform query shape.
    """

    __tablename__ = "usage_records"
    __table_args__ = (
        UniqueConstraint("organization_id", "period_start", "metric", name="uq_usage_org_period_metric"),
        # data-model.md: "(organization_id, metric)" -- billing reads filter
        # by metric within an Organization (e.g. "current ai_operations
        # usage") separately from the period_start-anchored uniqueness check.
        Index("ix_usage_records_organization_id_metric", "organization_id", "metric"),
    )

    period_start: dt.date = Field(nullable=False)
    period_end: dt.date = Field(nullable=False)
    metric: UsageMetric = Field(nullable=False)
    used_count: int = Field(default=0, nullable=False)
