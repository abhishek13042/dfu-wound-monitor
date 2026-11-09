"""Prometheus metrics with the ``dfu_`` prefix (REQ-P10-S01-002).

Labels stay low-cardinality: route templates, methods, status codes, failure
classes and outcomes.  User, case and analysis IDs are never labels.

Quality rejections are an outcome, not an error: they are counted in
``dfu_analyses_total{outcome="QUALITY_REJECTED"}`` and never in
``dfu_errors_total``.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest

log = logging.getLogger("dfu.metrics")
REGISTRY = CollectorRegistry(auto_describe=True)

HTTP_REQUESTS = Counter("dfu_http_requests_total", "HTTP requests handled", ("method", "route", "status"),
                        registry=REGISTRY)
HTTP_LATENCY = Histogram("dfu_http_request_duration_seconds", "HTTP request latency", ("method", "route"),
                         buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30), registry=REGISTRY)
ERRORS = Counter("dfu_errors_total", "Error responses and failed jobs, by failure class",
                 ("failure_class", "category", "source"), registry=REGISTRY)
QUEUE_DEPTH = Gauge("dfu_queue_depth", "Analysis jobs waiting in the queue", registry=REGISTRY)
JOB_DURATION = Histogram("dfu_job_duration_seconds", "Worker time per analysis job delivery", ("outcome",),
                         buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120, 300), registry=REGISTRY)
ANALYSES = Counter("dfu_analyses_total", "Finished analyses by outcome", ("outcome",), registry=REGISTRY)
MODEL_READY = Gauge("dfu_model_ready", "1 when a verified model can take jobs", registry=REGISTRY)

QUALITY_CLASS = "QUALITY"


def safely(action: Any, *args: Any, **kwargs: Any) -> None:
    """Telemetry never fails a request."""

    try:
        action(*args, **kwargs)
    except Exception as error:  # noqa: BLE001
        log.debug("metric update skipped: %s", type(error).__name__)


def record_request(method: str, route: str, status: int, seconds: float) -> None:
    safely(lambda: HTTP_REQUESTS.labels(method, route, str(status)).inc())
    safely(lambda: HTTP_LATENCY.labels(method, route).observe(seconds))


def record_error(failure_class: str, category: str, source: str = "api") -> None:
    if failure_class != QUALITY_CLASS:
        safely(lambda: ERRORS.labels(failure_class, category, source).inc())


def record_job(outcome: str, seconds: float) -> None:
    safely(lambda: JOB_DURATION.labels(outcome).observe(seconds))
    if outcome in ("COMPLETED", "QUALITY_REJECTED", "FAILED"):
        safely(lambda: ANALYSES.labels(outcome).inc())


def set_queue_depth(depth: int | None) -> None:
    if depth is not None:
        safely(QUEUE_DEPTH.set, depth)


def set_model_ready(ready: bool) -> None:
    safely(MODEL_READY.set, 1 if ready else 0)


def exposition() -> tuple[bytes, str]:
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


def start_worker_endpoint() -> int | None:
    """The worker has no HTTP server, so it exposes metrics on ``DFU_WORKER_METRICS_PORT`` when that is set."""

    port = os.environ.get("DFU_WORKER_METRICS_PORT")
    if not port:
        return None
    from prometheus_client import start_http_server

    try:
        start_http_server(int(port), addr=os.environ.get("DFU_WORKER_METRICS_ADDR", "127.0.0.1"), registry=REGISTRY)
    except OSError as error:
        log.warning("Worker metrics endpoint not started: %s", type(error).__name__)
        return None
    return int(port)
