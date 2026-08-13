"""T216/T217: end-to-end proof that a real request's correlation_id and
authenticated identity actually reach a log statement made deep in a route
handler — not just that the isolated pieces (JsonFormatter, bind_context)
work, which tests/unit/test_logging.py already covers.

This matters because of a real, easy-to-miss FastAPI gotcha found while
building this: a *sync* `Depends()` callable runs in a threadpool, and a
`contextvars.ContextVar.set()` made inside it never propagates back to the
request's own async context — `api/deps.py::get_current_user` was changed
from `def` to `async def` specifically so its `bind_context(...)` call
takes effect where it's supposed to. A test route (not a real endpoint) is
used here deliberately, so this test exercises the real, reusable
`CorrelationIdMiddleware` and `get_current_user` without requiring a log
statement to exist in production code purely to be observed by a test.
"""

import io
import json
import logging

import httpx
import pytest
from fastapi import Depends, FastAPI

from testpilot.api.deps import CurrentUser, get_current_user
from testpilot.auth.tokens import create_access_token
from testpilot.core.logging import ContextFilter, JsonFormatter
from testpilot.core.middleware import CorrelationIdMiddleware

pytestmark = pytest.mark.anyio


def _find_record(stream: io.StringIO, *, logger: str) -> dict[str, object]:
    """httpx's own logger (`httpx`) also emits an INFO line through the same
    root handler this test replaces, so the captured stream is one JSON
    object per line (NDJSON), not a single JSON document — pick out the
    one this test actually cares about."""
    for line in stream.getvalue().splitlines():
        record = json.loads(line)
        if record["logger"] == logger:
            return record
    raise AssertionError(f"no log record from logger {logger!r} was captured")


def _build_test_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/probe")
    async def probe(current_user: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
        logging.getLogger("test.probe").info("probe reached")
        return {"user_id": current_user.user_id}

    return app


@pytest.fixture
def captured_logs():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(ContextFilter())

    root = logging.getLogger()
    previous_handlers = root.handlers
    previous_level = root.level
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    try:
        yield stream
    finally:
        root.handlers = previous_handlers
        root.setLevel(previous_level)


async def test_a_real_authenticated_request_logs_correlation_and_identity(captured_logs):
    app = _build_test_app()
    token = create_access_token(user_id="11111111-1111-1111-1111-111111111111", organization_id="22222222-2222-2222-2222-222222222222")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/probe",
            headers={"Authorization": f"Bearer {token}", "X-Correlation-Id": "test-correlation-id"},
        )

    assert response.status_code == 200
    record = _find_record(captured_logs, logger="test.probe")
    assert record["message"] == "probe reached"
    assert record["correlation_id"] == "test-correlation-id"
    assert record["organization_id"] == "22222222-2222-2222-2222-222222222222"
    assert record["user_id"] == "11111111-1111-1111-1111-111111111111"


async def test_correlation_id_is_generated_when_the_caller_does_not_send_one(captured_logs):
    app = _build_test_app()
    token = create_access_token(user_id="33333333-3333-3333-3333-333333333333", organization_id="44444444-4444-4444-4444-444444444444")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/probe", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"]
    record = _find_record(captured_logs, logger="test.probe")
    assert record["correlation_id"] == response.headers["X-Correlation-Id"]
