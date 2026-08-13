import uuid
from enum import StrEnum

from sqlalchemy import Column, Computed, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlmodel import Field

from testpilot.core.models import TenantTable


class TestCasePriority(StrEnum):
    """Declared low-to-critical: Postgres sorts an enum column by this
    declaration order, not alphabetically, so `ORDER BY priority` is
    already meaningful without a separate rank mapping (FR-052)."""

    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class TestCaseSeverity(StrEnum):
    """Declared minor-to-blocker for the same ordering reason as TestCasePriority."""

    minor = "minor"
    major = "major"
    critical = "critical"
    blocker = "blocker"


class TestCaseStatus(StrEnum):
    draft = "draft"
    approved = "approved"
    rejected = "rejected"


class TestCaseSource(StrEnum):
    ai_generated = "ai_generated"
    manual = "manual"


class TestCaseResult(StrEnum):
    passed = "passed"
    failed = "failed"
    skipped = "skipped"
    not_run = "not_run"


class TestCase(TenantTable, table=True):
    """A single test scenario for a project (data-model.md `test_cases`,
    FR-041-FR-057). `search_vector` uses SQLAlchemy's `Computed(...)`
    (`GENERATED ALWAYS AS ... STORED`, FR-050) — mapped here (not omitted)
    so alembic's autogenerate sees it as intentional schema rather than
    drift to remove; `Computed` columns are automatically excluded from
    INSERT/UPDATE by SQLAlchemy, matching Postgres's own requirement that a
    GENERATED column never appear in an application-issued DML column list.
    testcases/service.py still queries it via a raw `text()` predicate
    (`@@ websearch_to_tsquery(...)`) since there's no ORM-level tsquery
    operator worth the added complexity for one predicate.
    """

    __tablename__ = "test_cases"
    __table_args__ = (
        Index("ix_test_cases_project_id_status", "project_id", "status"),
        Index("ix_test_cases_tags", "tags", postgresql_using="gin"),
        Index("ix_test_cases_search_vector", "search_vector", postgresql_using="gin"),
    )

    # ondelete="CASCADE" (not the `foreign_key="projects.id"` shorthand,
    # which has no ondelete option): fulfills DATA-005's "cascading delete
    # of test cases ... on hard delete" that projects/service.py's
    # delete_project() docstring deferred to "once Phase 8+ creates them".
    project_id: uuid.UUID = Field(
        sa_column=Column(SAUuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    title: str = Field(nullable=False)
    description: str = Field(nullable=False)
    priority: TestCasePriority = Field(nullable=False)
    severity: TestCaseSeverity = Field(nullable=False)
    status: TestCaseStatus = Field(default=TestCaseStatus.draft, nullable=False)
    source: TestCaseSource = Field(nullable=False)
    tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(Text), nullable=False, server_default="{}"),
    )
    last_result: TestCaseResult = Field(default=TestCaseResult.not_run, nullable=False)
    search_vector: str | None = Field(
        default=None,
        sa_column=Column(
            TSVECTOR,
            Computed("to_tsvector('english', title || ' ' || description)", persisted=True),
            nullable=True,
        ),
    )


class TestStepActionType(StrEnum):
    navigate = "navigate"
    click = "click"
    type = "type"
    submit = "submit"
    assert_url = "assert_url"
    assert_content = "assert_content"
    assert_element = "assert_element"


class TestStep(TenantTable, table=True):
    """One ordered action within a TestCase (data-model.md `test_steps`)."""

    __tablename__ = "test_steps"
    __table_args__ = (UniqueConstraint("test_case_id", "order_index", name="uq_test_steps_case_order"),)

    test_case_id: uuid.UUID = Field(
        sa_column=Column(SAUuid, ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    order_index: int = Field(nullable=False)
    action_type: TestStepActionType = Field(nullable=False)
    target_descriptor: str | None = None
    input_value: str | None = None
    expected_assertion: str | None = None
    # Not in data-model.md's column list — added in Phase 10 to make FR-064's
    # "MUST support capturing screenshots at other defined checkpoints"
    # (beyond the mandatory on-failure screenshot) an actually reachable
    # capability rather than an engine feature nothing can ever request.
    capture_screenshot: bool = Field(default=False, nullable=False, sa_column_kwargs={"server_default": "false"})
