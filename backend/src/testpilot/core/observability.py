"""Sentry error tracking on both the API and worker processes (NFR-012,
research.md #13).

`before_send` tags every captured event with the same
`correlation_id`/`organization_id`/`user_id` `core/logging.py` already
carries via `contextvars` — the same mechanism, not a second one — so an
error in Sentry can be cross-referenced against the exact log lines from
the same request/job without re-deriving identity by some other path.
"""

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.rq import RqIntegration
from sentry_sdk.types import Event, Hint

from testpilot.core.config import get_settings
from testpilot.core.logging import correlation_id_var, organization_id_var, user_id_var


def _attach_context_tags(event: Event, _hint: Hint) -> Event:
    tags = {}
    if (correlation_id := correlation_id_var.get()) is not None:
        tags["correlation_id"] = correlation_id
    if (organization_id := organization_id_var.get()) is not None:
        tags["organization_id"] = organization_id
    if (user_id := user_id_var.get()) is not None:
        tags["user_id"] = user_id
    if tags:
        event["tags"] = {**event.get("tags", {}), **tags}
    return event


def init_sentry() -> None:
    """No-op with no DSN configured — the default for local dev and every
    test environment (`.env`/`.env.test` deliberately omit `SENTRY_DSN`),
    so this is safe to call unconditionally at process startup rather than
    requiring every caller to check `settings.sentry_dsn` first."""
    settings = get_settings()
    if not settings.sentry_dsn:
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        integrations=[FastApiIntegration(), RqIntegration()],
        before_send=_attach_context_tags,
    )
