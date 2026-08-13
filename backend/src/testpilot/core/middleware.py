import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from testpilot.core.logging import bind_context

CORRELATION_ID_HEADER = "X-Correlation-Id"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Attaches a correlation ID to every request, reusing an inbound header
    if the caller already provided one, so a single user action can be traced
    across API logs, worker job logs, and error-tracking events (NFR-009).

    `bind_context` runs before `call_next` so the correlation ID is on the
    `contextvars.ContextVar` for the entire downstream request — including
    every log statement any route handler or service function makes — not
    just readable via `request.state` by code that happens to have the
    `Request` object in hand.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        correlation_id = request.headers.get(CORRELATION_ID_HEADER) or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        bind_context(correlation_id=correlation_id)
        response = await call_next(request)
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response
