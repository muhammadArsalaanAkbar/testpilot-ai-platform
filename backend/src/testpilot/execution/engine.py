"""`BrowserAutomationEngine` interface (contracts/browser-automation-adapter.md,
FR-068/NFR-019/INT-001).

`load_page` (Phase 9's prerequisite) and `run_test_case` (this phase, T125)
are both declared here — the full engine surface the contract specifies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Literal, Protocol

from testpilot.ai_provider.base import FormSnapshot, PageSnapshot

if TYPE_CHECKING:
    from testpilot.testcases.models import TestCase, TestStep

StepStatus = Literal["passed", "failed"]
TestResultStatus = Literal["passed", "failed", "error"]


@dataclass(frozen=True)
class LoadedPage:
    """What a real page load actually observed, before being reduced to the
    bounded `PageSnapshot` shape `ai_provider` consumes — kept separate so
    the engine boundary doesn't need to know about `ai_provider`'s prompt
    budget concerns."""

    url: str
    title: str
    headings: list[str]
    forms: list[FormSnapshot]
    interactive_elements: list[str]
    links: list[str] = field(default_factory=list)

    def to_page_snapshot(self) -> PageSnapshot:
        return PageSnapshot(
            url=self.url,
            title=self.title,
            headings=self.headings,
            forms=self.forms,
            interactive_elements=self.interactive_elements,
            links=self.links,
        )


@dataclass(frozen=True)
class StepExecutionRecord:
    """One entry in a TestResult's execution log (data-model.md
    `test_results.execution_log`'s documented shape: `{step_index,
    action_type, status, message, timestamp}`, FR-065)."""

    step_index: int
    action_type: str
    status: StepStatus
    message: str | None
    timestamp: datetime


@dataclass(frozen=True)
class CapturedArtifact:
    """A screenshot captured during a run_test_case call — raw bytes plus
    metadata, not yet persisted (contract: "the caller hands these to
    storage.save_artifact(...)" — this interface never talks to object
    storage directly, keeping storage a separate, swappable concern)."""

    step_index: int
    content_type: str
    data: bytes
    captured_at: datetime


@dataclass(frozen=True)
class TestResult:
    status: TestResultStatus
    execution_log: list[StepExecutionRecord]
    failure_step_index: int | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime
    duration_ms: int


class BrowserAutomationEngine(Protocol):
    async def load_page(self, url: str) -> LoadedPage: ...

    async def run_test_case(
        self, test_case: TestCase, steps: list[TestStep], target_url: str
    ) -> tuple[TestResult, list[CapturedArtifact]]: ...
