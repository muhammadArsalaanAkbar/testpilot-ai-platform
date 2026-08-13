"""T218: custom Prometheus counters/histograms for background job
observability (NFR-011, FR-138) — test execution throughput, AI request
latency/error rate, per contracts/worker-jobs.md's three job types. The
generic HTTP request metrics `prometheus-fastapi-instrumentator` records
automatically are not re-tested here; this covers only the custom
collectors this project adds on top of it.
"""

from prometheus_client import CollectorRegistry, generate_latest

from testpilot.core.metrics import (
    JOB_TYPES,
    QUEUE_NAMES,
    job_duration_seconds,
    jobs_total,
    queue_depth_collector,
    record_job_outcome,
)


def test_record_job_outcome_increments_the_success_counter():
    before = jobs_total.labels(job_type="test-execution", status="success")._value.get()
    record_job_outcome(job_type="test-execution", status="success", duration_seconds=1.5)
    after = jobs_total.labels(job_type="test-execution", status="success")._value.get()
    assert after == before + 1


def test_record_job_outcome_increments_the_failure_counter_independently_of_success():
    before_success = jobs_total.labels(job_type="ai-analysis", status="success")._value.get()
    before_failure = jobs_total.labels(job_type="ai-analysis", status="failure")._value.get()
    record_job_outcome(job_type="ai-analysis", status="failure", duration_seconds=0.2)
    assert jobs_total.labels(job_type="ai-analysis", status="success")._value.get() == before_success
    assert jobs_total.labels(job_type="ai-analysis", status="failure")._value.get() == before_failure + 1


def test_record_job_outcome_observes_duration_in_the_histogram():
    before_count = job_duration_seconds.labels(job_type="ai-generation")._sum.get()
    record_job_outcome(job_type="ai-generation", status="success", duration_seconds=2.5)
    after_count = job_duration_seconds.labels(job_type="ai-generation")._sum.get()
    assert after_count == before_count + 2.5


def test_job_types_matches_the_three_contracted_worker_jobs():
    assert {"ai-generation", "test-execution", "ai-analysis"} == JOB_TYPES


def test_queue_names_matches_the_three_contracted_queues():
    assert {"ai-generation", "test-execution", "ai-analysis"} == QUEUE_NAMES


def test_queue_depth_collector_reports_a_gauge_metric_per_queue():
    class _FakeQueue:
        def __init__(self, length: int) -> None:
            self._length = length

        def __len__(self) -> int:
            return self._length

    lengths = {"ai-generation": 3, "test-execution": 0, "ai-analysis": 7}
    collector = queue_depth_collector(lambda name: _FakeQueue(lengths[name]))

    registry = CollectorRegistry()
    registry.register(collector)
    output = generate_latest(registry).decode()

    assert 'testpilot_queue_depth{queue_name="ai-generation"} 3.0' in output
    assert 'testpilot_queue_depth{queue_name="test-execution"} 0.0' in output
    assert 'testpilot_queue_depth{queue_name="ai-analysis"} 7.0' in output
