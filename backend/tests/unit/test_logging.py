"""T216: structured JSON logging with correlation_id/organization_id/user_id
(NFR-009, FR-138). Verifies the formatter output shape and that context set
via bind_context() flows into whatever gets logged afterward, independent
of the request/worker plumbing that calls bind_context() in production.
"""

import io
import json
import logging

from testpilot.core.logging import (
    JsonFormatter,
    bind_context,
    configure_logging,
    correlation_id_var,
    current_or_new_correlation_id,
    organization_id_var,
    user_id_var,
)


def _make_logger_with_stream() -> tuple[logging.Logger, io.StringIO]:
    from testpilot.core.logging import ContextFilter

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(ContextFilter())
    logger = logging.getLogger(f"test-logger-{id(stream)}")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    return logger, stream


def test_json_formatter_emits_valid_json_with_expected_fields():
    logger, stream = _make_logger_with_stream()

    logger.info("hello world")

    record = json.loads(stream.getvalue())
    assert record["level"] == "INFO"
    assert record["message"] == "hello world"
    assert record["logger"] == logger.name
    assert "timestamp" in record
    assert record["correlation_id"] is None
    assert record["organization_id"] is None
    assert record["user_id"] is None


def test_bind_context_injects_correlation_organization_and_user_id():
    logger, stream = _make_logger_with_stream()

    correlation_token = correlation_id_var.set(None)
    organization_token = organization_id_var.set(None)
    user_token = user_id_var.set(None)
    try:
        bind_context(correlation_id="corr-123", organization_id="org-456", user_id="user-789")
        logger.info("scoped message")
    finally:
        correlation_id_var.reset(correlation_token)
        organization_id_var.reset(organization_token)
        user_id_var.reset(user_token)

    record = json.loads(stream.getvalue())
    assert record["correlation_id"] == "corr-123"
    assert record["organization_id"] == "org-456"
    assert record["user_id"] == "user-789"


def test_bind_context_only_overwrites_provided_fields():
    correlation_token = correlation_id_var.set("existing-correlation")
    organization_token = organization_id_var.set(None)
    try:
        bind_context(organization_id="org-only")
        assert correlation_id_var.get() == "existing-correlation"
        assert organization_id_var.get() == "org-only"
    finally:
        correlation_id_var.reset(correlation_token)
        organization_id_var.reset(organization_token)


def test_json_formatter_includes_exception_info():
    logger, stream = _make_logger_with_stream()

    try:
        raise ValueError("boom")
    except ValueError:
        logger.exception("something failed")

    record = json.loads(stream.getvalue())
    assert record["level"] == "ERROR"
    assert "ValueError: boom" in record["exception"]


def test_configure_logging_attaches_a_json_formatter_to_the_root_logger():
    configure_logging()
    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, JsonFormatter)


def test_current_or_new_correlation_id_reuses_an_already_bound_id():
    token = correlation_id_var.set("already-bound")
    try:
        assert current_or_new_correlation_id() == "already-bound"
    finally:
        correlation_id_var.reset(token)


def test_current_or_new_correlation_id_mints_one_when_unset():
    token = correlation_id_var.set(None)
    try:
        minted = current_or_new_correlation_id()
        assert minted
        assert minted != current_or_new_correlation_id()  # each call with none bound mints a fresh one
    finally:
        correlation_id_var.reset(token)
