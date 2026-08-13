"""`artifacts` model (data-model.md `artifacts`, T148) — metadata/reference
only (DATA-002: the binary itself lives in object storage, never this row).

Separate module from `execution/models.py` per tasks.md's own file split
(T136 vs T148), even though both live in the same `execution` library and
share the same RLS-table conventions.
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Column, ForeignKey, Index
from sqlalchemy import Uuid as SAUuid
from sqlmodel import Field, SQLModel

from testpilot.core.models import IDMixin, OrgScopedMixin, tz_datetime_field


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ArtifactType(StrEnum):
    screenshot = "screenshot"
    log = "log"


class Artifact(IDMixin, OrgScopedMixin, SQLModel, table=True):
    """A captured screenshot/log's storage reference (data-model.md
    `artifacts`, FR-064/FR-072, DATA-002/DATA-003)."""

    __tablename__ = "artifacts"
    __table_args__ = (Index("ix_artifacts_test_result_id", "test_result_id"),)

    test_result_id: uuid.UUID = Field(
        sa_column=Column(SAUuid, ForeignKey("test_results.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    type: ArtifactType = Field(nullable=False)
    # Nullable: DATA-003's retention purge nulls this once the binary is
    # deleted from object storage, while the row (and the parent
    # TestResult's outcome) survives — see worker/jobs/purge_artifacts.py.
    storage_key: str | None = Field(default=None, nullable=True)
    content_type: str = Field(nullable=False)
    size_bytes: int = Field(nullable=False)
    captured_at: datetime = tz_datetime_field(nullable=False, default_factory=_utcnow)
