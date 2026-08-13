"""T218/T219: worker process entrypoint (plan.md's "one worker deployable,
different CMD" — the RQ worker's `main()`, analogous to `api/main.py`'s
`create_app()`). Verifies the process-startup wiring itself — logging,
Sentry init, metrics HTTP server, and which queues the `Worker` listens
on — without actually running RQ's blocking `work()` loop.
"""

from unittest.mock import MagicMock, patch

from testpilot.worker.main import build_worker


def test_build_worker_listens_on_all_three_contracted_queues():
    with patch("testpilot.worker.main.Worker") as mock_worker_cls:
        build_worker()

    _args, kwargs = mock_worker_cls.call_args
    queues = kwargs.get("queues") or mock_worker_cls.call_args[0][0]
    queue_names = {q.name for q in queues}
    assert queue_names == {"ai-generation", "test-execution", "ai-analysis"}


def test_main_configures_logging_sentry_and_starts_the_metrics_server():
    with (
        patch("testpilot.worker.main.configure_logging") as mock_configure_logging,
        patch("testpilot.worker.main.init_sentry") as mock_init_sentry,
        patch("testpilot.worker.main.start_http_server") as mock_start_http_server,
        patch("testpilot.worker.main.build_worker") as mock_build_worker,
    ):
        mock_worker = MagicMock()
        mock_build_worker.return_value = mock_worker

        from testpilot.worker.main import main

        main()

    mock_configure_logging.assert_called_once()
    mock_init_sentry.assert_called_once()
    mock_start_http_server.assert_called_once()
    mock_worker.work.assert_called_once()
