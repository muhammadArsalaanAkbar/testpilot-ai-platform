"""Request/response schemas for the Test Cases API (contracts/test-cases-api.md)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from testpilot.testcases.models import (
    TestCasePriority,
    TestCaseResult,
    TestCaseSeverity,
    TestCaseSource,
    TestCaseStatus,
    TestStepActionType,
)


class TestStepInput(BaseModel):
    """`order_index` is optional here: manual creation via the API/frontend
    can just supply steps in the intended order and let the service assign
    indices positionally, rather than requiring the caller to compute them."""

    order_index: int | None = None
    action_type: TestStepActionType
    target_descriptor: str | None = None
    input_value: str | None = None
    expected_assertion: str | None = None
    capture_screenshot: bool = False


class TestStepPublic(BaseModel):
    order_index: int
    action_type: TestStepActionType
    target_descriptor: str | None
    input_value: str | None
    expected_assertion: str | None
    capture_screenshot: bool


class TestCasePublic(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str
    priority: TestCasePriority
    severity: TestCaseSeverity
    status: TestCaseStatus
    source: TestCaseSource
    tags: list[str]
    last_result: TestCaseResult
    created_at: datetime
    updated_at: datetime


class TestCasesListResponse(BaseModel):
    items: list[TestCasePublic]


class CreateTestCaseRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1)
    priority: TestCasePriority
    severity: TestCaseSeverity
    tags: list[str] = []
    steps: list[TestStepInput] = []


class UpdateTestCaseRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, min_length=1)
    priority: TestCasePriority | None = None
    severity: TestCaseSeverity | None = None
    tags: list[str] | None = None
    steps: list[TestStepInput] | None = None


class TestCaseDetailResponse(BaseModel):
    test_case: TestCasePublic
    steps: list[TestStepPublic]
    # Populated once test runs exist (Phase 11/12); an empty list is the
    # correct MVP-so-far value, not a placeholder.
    recent_results: list[Any] = []
