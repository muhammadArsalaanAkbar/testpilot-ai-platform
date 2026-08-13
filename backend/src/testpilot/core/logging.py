"""Structured JSON logging (NFR-009, FR-138, research.md #13).

Stdlib `logging` plus a JSON formatter — no extra dependency, per
research.md #13's Simplicity-principle rationale for choosing this over a
dedicated framework like `structlog`. `correlation_id`/`organization_id`/
`user_id` are carried via `contextvars` (not passed explicitly to every log
call) so any code on the call stack of a request or worker job — service
layer included — gets them on every log record for free, once the
request/job entrypoint has called `bind_context(...)` once.
"""

import contextvars
import json
import logging
import uuid
from datetime import UTC, datetime

correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)
organization_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "organization_id", default=None
)
user_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("user_id", default=None)


def bind_context(
    *,
    correlation_id: str | None = None,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> None:
    """Sets whichever of the three context fields the caller knows at this
    point. Each is independent — e.g. the correlation-ID middleware runs
    before authentication resolves `user_id`, and calls this again once
    `get_current_user` knows it, without disturbing the correlation ID
    already set."""
    if correlation_id is not None:
        correlation_id_var.set(correlation_id)
    if organization_id is not None:
        organization_id_var.set(organization_id)
    if user_id is not None:
        user_id_var.set(user_id)


def current_or_new_correlation_id() -> str:
    """The in-flight request's correlation ID if one is set (API routes —
    `CorrelationIdMiddleware` already set it), otherwise a fresh one. Used
    at every job-enqueue call site (contracts/worker-jobs.md's envelope)
    so a CLI invocation, which has no request to inherit a correlation ID
    from, still gets one rather than propagating `None` into the job."""
    return correlation_id_var.get() or str(uuid.uuid4())


class ContextFilter(logging.Filter):
    """Attaches the current contextvar values to every log record passing
    through a handler this filter is installed on."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get()
        record.organization_id = organization_id_var.get()
        record.user_id = user_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line — machine-parseable per NFR-009, and the
    shape a log-aggregation backend (CloudWatch, Loki, etc.) expects."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", None),
            "organization_id": getattr(record, "organization_id", None),
            "user_id": getattr(record, "user_id", None),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(*, level: int = logging.INFO) -> None:
    """Replaces the root logger's handlers with a single JSON-formatted
    stream handler carrying the context filter — called once at process
    startup (API and worker both), never per-request."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(ContextFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
