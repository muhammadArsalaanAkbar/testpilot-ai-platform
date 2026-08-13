"""Worker process entrypoint (plan.md: "one worker deployable ...
different entrypoint/CMD" — `infra/docker/backend.Dockerfile`'s worker CMD
runs this module). Analogous to `api/main.py`'s `create_app()`, but for
the RQ worker process rather than the FastAPI app.
"""

from prometheus_client import start_http_server
from rq import Worker

from testpilot.core.config import get_settings
from testpilot.core.logging import configure_logging
from testpilot.core.observability import init_sentry
from testpilot.worker.queues import (
    ai_analysis_queue,
    ai_generation_queue,
    get_sync_redis,
    test_execution_queue,
)


def build_worker() -> Worker:
    return Worker(
        queues=[ai_generation_queue(), test_execution_queue(), ai_analysis_queue()],
        connection=get_sync_redis(),
    )


def main() -> None:
    configure_logging()
    init_sentry()  # NFR-012. No-op unless SENTRY_DSN is configured.
    # NFR-011: job-duration/error-rate counters (core/metrics.py) are
    # recorded by worker/jobs/*.py in this same process — this HTTP server
    # is what makes them scrapeable, separately from the API's own
    # /metrics (api/v1/health.py), since this process has no FastAPI app
    # of its own.
    start_http_server(get_settings().worker_metrics_port)
    worker = build_worker()
    worker.work()


if __name__ == "__main__":
    main()
