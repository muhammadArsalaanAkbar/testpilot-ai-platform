"""T219: Sentry SDK wiring on both API and worker processes (NFR-012).
Verifies `init_sentry()`'s own logic in isolation — whether it calls
`sentry_sdk.init(...)` at all (must be a no-op with no DSN configured, the
default for local/test environments) and that its `before_send` hook
attaches `correlation_id`/`organization_id`/`user_id` tags from the same
context `core/logging.py` already populates, so an error in Sentry can be
cross-referenced against the exact log lines from the same request/job
(the explicit NFR-012 requirement) without re-deriving them by some other
path.
"""

from unittest.mock import patch

from testpilot.core.logging import correlation_id_var, organization_id_var, user_id_var
from testpilot.core.observability import _attach_context_tags, init_sentry


def test_init_sentry_is_a_no_op_when_no_dsn_is_configured():
    with (
        patch("testpilot.core.observability.get_settings") as mock_get_settings,
        patch("testpilot.core.observability.sentry_sdk.init") as mock_init,
    ):
        mock_get_settings.return_value.sentry_dsn = None
        init_sentry()

    mock_init.assert_not_called()


def test_init_sentry_initializes_the_sdk_when_a_dsn_is_configured():
    with (
        patch("testpilot.core.observability.get_settings") as mock_get_settings,
        patch("testpilot.core.observability.sentry_sdk.init") as mock_init,
    ):
        mock_get_settings.return_value.sentry_dsn = "https://example@o0.ingest.sentry.io/0"
        mock_get_settings.return_value.environment = "staging"
        init_sentry()

    mock_init.assert_called_once()
    _args, kwargs = mock_init.call_args
    assert kwargs["dsn"] == "https://example@o0.ingest.sentry.io/0"
    assert kwargs["environment"] == "staging"
    assert kwargs["before_send"] is _attach_context_tags


def test_attach_context_tags_adds_correlation_organization_and_user_id():
    correlation_token = correlation_id_var.set("corr-obs-1")
    organization_token = organization_id_var.set("org-obs-2")
    user_token = user_id_var.set("user-obs-3")
    try:
        event = _attach_context_tags({"message": "boom"}, {})
    finally:
        correlation_id_var.reset(correlation_token)
        organization_id_var.reset(organization_token)
        user_id_var.reset(user_token)

    assert event["tags"]["correlation_id"] == "corr-obs-1"
    assert event["tags"]["organization_id"] == "org-obs-2"
    assert event["tags"]["user_id"] == "user-obs-3"


def test_attach_context_tags_omits_unset_fields():
    correlation_token = correlation_id_var.set(None)
    organization_token = organization_id_var.set(None)
    user_token = user_id_var.set(None)
    try:
        event = _attach_context_tags({"message": "boom"}, {})
    finally:
        correlation_id_var.reset(correlation_token)
        organization_id_var.reset(organization_token)
        user_id_var.reset(user_token)

    assert "tags" not in event or event["tags"] == {}


def test_attach_context_tags_always_returns_the_event_unchanged_otherwise():
    event = _attach_context_tags({"message": "boom", "level": "error"}, {})
    assert event["message"] == "boom"
    assert event["level"] == "error"
