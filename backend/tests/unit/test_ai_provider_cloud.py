"""Unit tests for the cloud LLMProvider adapter's parsing/error-mapping
logic, via a mocked Anthropic client (dependency injection) — this adapter's
own live-provider contract test is intentionally gated/infrequent per
plan.md's AI Test-Case Generation Architecture testing note, not part of
this suite; these tests cover the logic that doesn't require network access.
"""

import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock

import anthropic
import httpx
import pytest

from testpilot.ai_provider.base import (
    AIProviderError,
    FailureContext,
    PageSnapshot,
    SiteAnalysisContext,
)
from testpilot.ai_provider.cloud import CloudLLMProvider

pytestmark = pytest.mark.anyio


def _failure_context(**overrides: object) -> FailureContext:
    defaults: dict[str, object] = {
        "step_action_type": "assert_content",
        "step_target_descriptor": None,
        "step_expected_assertion": "Welcome",
        "actual_state": "Element not found",
        "execution_log": ["Step 0: navigate -> passed", "Step 1: assert_content -> failed"],
        "screenshot_reference": "https://storage.example/signed-url",
    }
    defaults.update(overrides)
    return FailureContext(**defaults)  # type: ignore[arg-type]


def _analysis_tool_response() -> SimpleNamespace:
    return _tool_use_response(
        {
            "explanation": "The expected text never appeared.",
            "root_cause": "The page failed to render the welcome banner.",
            "severity": "major",
            "suggested_fix": "Check the banner component's render condition.",
            "expected_vs_actual": "Expected: Welcome. Actual: Element not found.",
        }
    )


class _FakeHttpxResponse:
    def __init__(self, content: bytes, content_type: str = "image/png", status_code: int = 200) -> None:
        self.content = content
        self.headers = {"content-type": content_type}
        self._status_code = status_code

    def raise_for_status(self) -> None:
        if self._status_code >= 400:
            raise httpx.HTTPStatusError("error", request=httpx.Request("GET", "https://x"), response=httpx.Response(self._status_code))


class _FakeHttpxClient:
    def __init__(self, response: _FakeHttpxResponse | None = None, raises: Exception | None = None) -> None:
        self._response = response
        self._raises = raises

    async def __aenter__(self) -> "_FakeHttpxClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def get(self, url: str, timeout: float = 10.0) -> _FakeHttpxResponse:
        if self._raises is not None:
            raise self._raises
        assert self._response is not None
        return self._response


def _tool_use_response(input_payload: dict) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", input=input_payload)],
        usage=SimpleNamespace(input_tokens=100, output_tokens=50),
    )


async def test_generate_test_cases_parses_a_valid_tool_use_response():
    mock_client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock()))
    mock_client.messages.create.return_value = _tool_use_response(
        {
            "test_cases": [
                {
                    "title": "Sign up with valid details",
                    "description": "Confirms signup succeeds with valid input.",
                    "priority": "high",
                    "severity": "major",
                    "flow_type": "positive",
                    "steps": [{"action_type": "navigate", "target_descriptor": "/signup"}],
                }
            ]
        }
    )
    provider = CloudLLMProvider(client=mock_client, model="claude-sonnet-5")
    context = SiteAnalysisContext(
        project_name="Example",
        project_url="https://example.com",
        pages=[PageSnapshot(url="https://example.com", title="Home", headings=[], forms=[], interactive_elements=[], links=[])],
    )

    batch = await provider.generate_test_cases(context)

    assert len(batch.test_cases) == 1
    assert batch.test_cases[0].title == "Sign up with valid details"
    assert batch.tokens_used == 150


async def test_generate_test_cases_raises_when_no_tool_use_block_returned():
    mock_client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock()))
    mock_client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="I can't do that")],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )
    provider = CloudLLMProvider(client=mock_client, model="claude-sonnet-5")
    context = SiteAnalysisContext(project_name="Example", project_url="https://example.com", pages=[])

    with pytest.raises(AIProviderError) as exc_info:
        await provider.generate_test_cases(context)
    assert exc_info.value.retryable is False


async def test_generate_test_cases_raises_on_malformed_tool_input():
    mock_client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock()))
    mock_client.messages.create.return_value = _tool_use_response({"test_cases": [{"title": "missing fields"}]})
    provider = CloudLLMProvider(client=mock_client, model="claude-sonnet-5")
    context = SiteAnalysisContext(project_name="Example", project_url="https://example.com", pages=[])

    with pytest.raises(AIProviderError) as exc_info:
        await provider.generate_test_cases(context)
    assert exc_info.value.retryable is False


async def test_generate_test_cases_maps_timeout_to_retryable_error():
    mock_client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock()))
    mock_client.messages.create.side_effect = anthropic.APITimeoutError(request=httpx.Request("POST", "https://api.anthropic.com"))
    provider = CloudLLMProvider(client=mock_client, model="claude-sonnet-5")
    context = SiteAnalysisContext(project_name="Example", project_url="https://example.com", pages=[])

    with pytest.raises(AIProviderError) as exc_info:
        await provider.generate_test_cases(context)
    assert exc_info.value.retryable is True


async def test_generate_test_cases_maps_server_error_to_retryable_error():
    request = httpx.Request("POST", "https://api.anthropic.com")
    response = httpx.Response(500, request=request)
    mock_client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock()))
    mock_client.messages.create.side_effect = anthropic.InternalServerError(
        message="server error", response=response, body=None
    )
    provider = CloudLLMProvider(client=mock_client, model="claude-sonnet-5")
    context = SiteAnalysisContext(project_name="Example", project_url="https://example.com", pages=[])

    with pytest.raises(AIProviderError) as exc_info:
        await provider.generate_test_cases(context)
    assert exc_info.value.retryable is True


async def test_generate_test_cases_maps_client_error_to_non_retryable_error():
    request = httpx.Request("POST", "https://api.anthropic.com")
    response = httpx.Response(400, request=request)
    mock_client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock()))
    mock_client.messages.create.side_effect = anthropic.BadRequestError(
        message="bad request", response=response, body=None
    )
    provider = CloudLLMProvider(client=mock_client, model="claude-sonnet-5")
    context = SiteAnalysisContext(project_name="Example", project_url="https://example.com", pages=[])

    with pytest.raises(AIProviderError) as exc_info:
        await provider.generate_test_cases(context)
    assert exc_info.value.retryable is False


async def test_analyze_failure_parses_a_valid_tool_use_response(monkeypatch):
    mock_client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock()))
    mock_client.messages.create.return_value = _analysis_tool_response()
    monkeypatch.setattr(httpx, "AsyncClient", lambda: _FakeHttpxClient(_FakeHttpxResponse(b"png-bytes")))
    provider = CloudLLMProvider(client=mock_client, model="claude-sonnet-5")

    analysis = await provider.analyze_failure(_failure_context())

    assert analysis.explanation == "The expected text never appeared."
    assert analysis.root_cause == "The page failed to render the welcome banner."
    assert analysis.severity == "major"
    assert analysis.suggested_fix == "Check the banner component's render condition."
    assert analysis.expected_vs_actual == "Expected: Welcome. Actual: Element not found."


async def test_analyze_failure_includes_a_fetched_screenshot_in_the_request(monkeypatch):
    mock_client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock()))
    mock_client.messages.create.return_value = _analysis_tool_response()
    monkeypatch.setattr(httpx, "AsyncClient", lambda: _FakeHttpxClient(_FakeHttpxResponse(b"real-png-bytes")))
    provider = CloudLLMProvider(client=mock_client, model="claude-sonnet-5")

    await provider.analyze_failure(_failure_context())

    sent_messages = mock_client.messages.create.call_args.kwargs["messages"]
    content_blocks = sent_messages[0]["content"]
    assert content_blocks[0]["type"] == "text"
    image_blocks = [b for b in content_blocks if b["type"] == "image"]
    assert len(image_blocks) == 1
    assert image_blocks[0]["source"]["media_type"] == "image/png"
    decoded = base64.b64decode(image_blocks[0]["source"]["data"])
    assert decoded == b"real-png-bytes"


async def test_analyze_failure_degrades_gracefully_when_screenshot_fetch_fails(monkeypatch):
    """spec Edge Cases: a screenshot/log artifact that can't be retrieved
    must not fail the whole analysis — it proceeds text-only."""
    mock_client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock()))
    mock_client.messages.create.return_value = _analysis_tool_response()
    monkeypatch.setattr(httpx, "AsyncClient", lambda: _FakeHttpxClient(raises=httpx.ConnectError("unreachable")))
    provider = CloudLLMProvider(client=mock_client, model="claude-sonnet-5")

    analysis = await provider.analyze_failure(_failure_context())

    assert analysis.explanation == "The expected text never appeared."
    sent_messages = mock_client.messages.create.call_args.kwargs["messages"]
    content_blocks = sent_messages[0]["content"]
    assert all(b["type"] == "text" for b in content_blocks)


async def test_analyze_failure_skips_fetch_when_no_screenshot_reference(monkeypatch):
    mock_client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock()))
    mock_client.messages.create.return_value = _analysis_tool_response()

    def _unexpected_client() -> _FakeHttpxClient:
        raise AssertionError("should not fetch when there is no screenshot_reference")

    monkeypatch.setattr(httpx, "AsyncClient", _unexpected_client)
    provider = CloudLLMProvider(client=mock_client, model="claude-sonnet-5")

    analysis = await provider.analyze_failure(_failure_context(screenshot_reference=""))

    assert analysis.explanation == "The expected text never appeared."


async def test_analyze_failure_maps_timeout_to_retryable_error(monkeypatch):
    mock_client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock()))
    mock_client.messages.create.side_effect = anthropic.APITimeoutError(request=httpx.Request("POST", "https://api.anthropic.com"))
    monkeypatch.setattr(httpx, "AsyncClient", lambda: _FakeHttpxClient(_FakeHttpxResponse(b"bytes")))
    provider = CloudLLMProvider(client=mock_client, model="claude-sonnet-5")

    with pytest.raises(AIProviderError) as exc_info:
        await provider.analyze_failure(_failure_context())
    assert exc_info.value.retryable is True


async def test_analyze_failure_raises_on_malformed_tool_input(monkeypatch):
    mock_client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock()))
    mock_client.messages.create.return_value = _tool_use_response({"explanation": "missing other fields"})
    monkeypatch.setattr(httpx, "AsyncClient", lambda: _FakeHttpxClient(_FakeHttpxResponse(b"bytes")))
    provider = CloudLLMProvider(client=mock_client, model="claude-sonnet-5")

    with pytest.raises(AIProviderError) as exc_info:
        await provider.analyze_failure(_failure_context())
    assert exc_info.value.retryable is False
