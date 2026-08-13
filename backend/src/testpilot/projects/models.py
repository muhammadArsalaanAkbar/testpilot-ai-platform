from enum import StrEnum
from typing import Any

from sqlalchemy import Column, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from testpilot.core.models import TenantTable


class ProjectStatus(StrEnum):
    active = "active"
    archived = "archived"


class Project(TenantTable, table=True):
    """A target website under test (data-model.md `projects`, FR-025-FR-035)."""

    __tablename__ = "projects"
    __table_args__ = (Index("ix_projects_organization_id_status", "organization_id", "status"),)

    name: str = Field(nullable=False)
    url: str = Field(nullable=False)
    status: ProjectStatus = Field(default=ProjectStatus.active, nullable=False)
    settings: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
