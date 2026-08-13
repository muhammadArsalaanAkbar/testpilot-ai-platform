"""Custom Prometheus metrics for background-job observability (NFR-011,
FR-138, research.md #13). `prometheus-fastapi-instrumentator` (wired in
`api/main.py`) already covers generic HTTP request metrics automatically;
this module covers what it cannot see — the three job types defined in
contracts/worker-jobs.md (test execution throughput, AI request
latency/error rate) and per-queue depth.

Job-duration/error-rate counters are recorded by the worker job handlers
themselves (`worker/jobs/*.py`), in the worker process — `worker/main.py`
exposes them on their own metrics HTTP port via `prometheus_client`'s
default global registry, since a worker process has no FastAPI app of its
own for `prometheus-fastapi-instrumentator` to instrument. Queue depth is
exposed from the API's `/metrics` (api/v1/health.py) instead: it is live
Redis state, not something either process's own execution history
accumulates, so there's nothing gained by recording it from the worker
specifically.
"""

from collections.abc import Callable, Sized

from prometheus_client import Counter, Histogram
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector

JOB_TYPES = {"ai-generation", "test-execution", "ai-analysis"}
QUEUE_NAMES = {"ai-generation", "test-execution", "ai-analysis"}

jobs_total = Counter(
    "testpilot_jobs_total",
    "Background jobs processed, by job type and outcome.",
    labelnames=["job_type", "status"],
)

job_duration_seconds = Histogram(
    "testpilot_job_duration_seconds",
    "Background job processing duration in seconds, by job type.",
    labelnames=["job_type"],
)


def record_job_outcome(*, job_type: str, status: str, duration_seconds: float) -> None:
    """Called once per job handler invocation, in a `finally` block so both
    success and failure are recorded (contracts/worker-jobs.md's retry
    section — a permanent failure still needs to count toward the
    error-rate metric NFR-011 asks for)."""
    jobs_total.labels(job_type=job_type, status=status).inc()
    job_duration_seconds.labels(job_type=job_type).observe(duration_seconds)


def queue_depth_collector(get_queue: Callable[[str], Sized]) -> Collector:
    """Builds a Prometheus `Collector` that reads current queue lengths at
    scrape time (a Gauge callback, not a value maintained incrementally by
    the API process — queue depth changes from both enqueue, in the API/CLI
    processes, and dequeue, in the worker process, so no single process's
    in-memory counter could stay accurate).

    `get_queue` is injected (rather than importing `worker.queues` here
    directly) so this stays testable with a fake queue object — real usage
    passes a function resolving to the real RQ `Queue` per
    `worker/queues.py`, whose `__len__` already returns the pending job
    count."""

    class _QueueDepthCollector:
        def collect(self):  # type: ignore[no-untyped-def]
            metric = GaugeMetricFamily(
                "testpilot_queue_depth", "Pending job count per queue.", labels=["queue_name"]
            )
            for queue_name in sorted(QUEUE_NAMES):
                metric.add_metric([queue_name], len(get_queue(queue_name)))
            yield metric

    return _QueueDepthCollector()
