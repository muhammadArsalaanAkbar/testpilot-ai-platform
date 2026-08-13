"""LLMProvider Protocol — the provider-agnostic AI boundary.

NFR-018/INT-002: callers (`ai_generation`, `ai_analysis`, the Future `assistant`
library) depend only on this interface, never on a specific provider SDK's
types. Every concrete adapter (fake.py for tests, cloud.py for production)
satisfies this Protocol. See contracts/ai-provider-adapter.md for the full
contract this module implements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

FlowType = Literal["positive", "negative", "edge_case"]
Priority = Literal["low", "medium", "high", "critical"]
Severity = Literal["minor", "major", "critical", "blocker"]
StepActionType = Literal[
    "navigate", "click", "type", "submit", "assert_url", "assert_content", "assert_element"
]


class AIProviderError(Exception):
    """Raised by an adapter on provider error/timeout/malformed output after
    the adapter's own internal bounded retry (contract: "never returns a
    partially-valid batch"). Callers apply FR-046's bounded-retry-then-
    fail-clean policy at the job level, never regex-parse free text.
    """

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


# --- generate_test_cases ----------------------------------------------------


@dataclass(frozen=True)
class FormFieldSnapshot:
    name: str
    field_type: str
    label: str | None = None


@dataclass(frozen=True)
class FormSnapshot:
    action: str | None
    method: str | None
    fields: list[FormFieldSnapshot]


@dataclass(frozen=True)
class PageSnapshot:
    """Bounded structured extraction of one reachable public page — never
    raw HTML (contract: "a bounded structured extraction... never raw
    full-page HTML")."""

    url: str
    title: str
    headings: list[str]
    forms: list[FormSnapshot]
    interactive_elements: list[str]
    links: list[str]


@dataclass(frozen=True)
class SiteAnalysisContext:
    project_name: str
    project_url: str
    pages: list[PageSnapshot]
    preferences: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GeneratedTestStep:
    action_type: StepActionType
    target_descriptor: str | None = None
    input_value: str | None = None
    expected_assertion: str | None = None


@dataclass(frozen=True)
class GeneratedTestCase:
    title: str
    description: str
    priority: Priority
    severity: Severity
    flow_type: FlowType
    steps: list[GeneratedTestStep]


@dataclass(frozen=True)
class GeneratedTestCaseBatch:
    test_cases: list[GeneratedTestCase]
    tokens_used: int = 0


# --- analyze_failure (Phase 13 caller; Protocol declared now per contract) --


@dataclass(frozen=True)
class FailureContext:
    step_action_type: StepActionType
    step_target_descriptor: str | None
    step_expected_assertion: str | None
    actual_state: str
    execution_log: list[str]
    screenshot_reference: str


@dataclass(frozen=True)
class FailureAnalysis:
    explanation: str
    root_cause: str
    severity: Severity
    suggested_fix: str
    expected_vs_actual: str


# --- chat (Future AI QA Assistant; Protocol declared now per contract) ------


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class ChatContext:
    messages: list[ChatMessage]
    grounding_data: dict[str, Any] | None = None


@dataclass(frozen=True)
class ChatResponse:
    message: str
    grounded: bool = False
    referenced_entities: list[str] = field(default_factory=list)


class LLMProvider(Protocol):
    # Identity, for attributing a persisted result to the adapter/model that
    # produced it (data-model.md ai_analyses.provider/model, T160) — every
    # concrete adapter sets these as class/instance attributes.
    provider_name: str
    model: str

    async def generate_test_cases(self, context: SiteAnalysisContext) -> GeneratedTestCaseBatch: ...

    async def analyze_failure(self, context: FailureContext) -> FailureAnalysis: ...

    async def chat(self, context: ChatContext) -> ChatResponse: ...
