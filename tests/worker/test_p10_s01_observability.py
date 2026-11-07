"""P10-S01: one ID from request to job, scrubbed logs, metrics, and telemetry that never fails a request."""

from __future__ import annotations

import io
import json
import logging

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.errors import ApiError
from src.observability import configure_logging, scrub
from src.observability import metrics as m
from src.observability.context import accept_request_id
from src.worker import tasks
from src.worker.state import COMPLETED, FAILED, QUALITY_REJECTED
from src.worker.tasks import process_job, run_job
from tests.worker.conftest import verified_upload

TRACE = "trace-fault-0001"


@pytest.fixture
def logs():
    stream = io.StringIO()
    configure_logging("test", stream=stream, force=True)
    yield lambda: [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]
    configure_logging("test", force=True)


def _sample(name: str, **labels) -> float:
    return m.REGISTRY.get_sample_value(name, labels) or 0.0


def _submit(client: TestClient, image: bytes, request_id: str = TRACE) -> str:
    upload_id = verified_upload(client, image)
    response = client.post("/api/v2/analyses", json={"upload_id": upload_id}, headers={"X-Request-ID": request_id})
    assert response.status_code == 202, response.text
    assert response.headers["X-Request-ID"] == request_id
    return response.json()["analysis_id"]


# ------------------------------------------------------------- REQ-001: one ID
def test_every_response_carries_a_request_id(client):
    first, second = client.get("/health/live"), client.get("/health/live")
    assert first.headers["X-Request-ID"].startswith("req_")
    assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]


def test_a_supplied_id_is_kept_and_a_malformed_one_is_replaced(client):
    assert client.get("/health/live", headers={"X-Request-ID": "caller-123456"}).headers["X-Request-ID"] == "caller-123456"
    replaced = client.get("/health/live", headers={"X-Request-ID": "bad id\nInjected: 1"}).headers["X-Request-ID"]
    assert replaced.startswith("req_")
    assert accept_request_id("x" * 65).startswith("req_")


def test_error_body_names_the_same_id_as_the_header(client):
    response = client.get("/api/v2/analyses/ana_missing", headers={"X-Request-ID": TRACE})
    assert response.status_code == 404
    assert response.json()["request_id"] == TRACE == response.headers["X-Request-ID"]


def test_the_id_follows_the_job_into_the_worker_and_the_result(client, state, image, logs):
    analysis_id = _submit(client, image)
    assert state.db.load_job(analysis_id)["request"]["request_id"] == TRACE
    assert process_job(state, analysis_id).status == COMPLETED
    worker_lines = [line for line in logs() if line.get("analysis_id") == analysis_id]
    assert {line["message"] for line in worker_lines} == {"job started", "job finished"}
    assert {line["request_id"] for line in worker_lines} == {TRACE}
    assert client.get(f"/api/v2/analyses/{analysis_id}").json()["provenance"]["request_id"] == TRACE


def test_access_log_uses_the_route_template_not_the_raw_path(client, logs):
    client.get("/api/v2/analyses/ana_secretlookingid", headers={"X-Request-ID": TRACE})
    access = [line for line in logs() if line["message"] == "request"]
    assert access and access[-1]["route"] == "/api/v2/analyses/{analysis_id}"
    assert "ana_secretlookingid" not in json.dumps(access)


# ------------------------------------------------------- REQ-003: no secrets in logs
PLANTED = {
    "bearer": "Authorization: Bearer abc.def-ghi_jkl",
    "jwt": "token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.c2lnbmF0dXJl",
    "query": "GET /blob?signature=s3cr3tsig&token=t0k3n",
    "filename": 'filename="Mrs Smith left foot.jpg"',
    "inline": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk",
    "base64": "A" * 400,
    "bytes": repr(bytes(range(128, 160))),
}


@pytest.mark.parametrize("kind", sorted(PLANTED))
def test_scrub_removes_planted_secrets(kind):
    planted = PLANTED[kind]
    cleaned = scrub(f"before {planted} after")
    assert "[redacted]" in cleaned and cleaned.startswith("before") and cleaned.endswith("after")
    for secret in ("abc.def-ghi_jkl", "eyJhbGciOiJIUzI1NiJ9", "s3cr3tsig", "t0k3n", "Mrs Smith", "iVBORw0KGgo", "A" * 200,
                   "\\x80\\x81\\x82"):
        assert secret not in cleaned


def test_secrets_in_messages_arguments_and_tracebacks_are_scrubbed(logs):
    log = logging.getLogger("dfu.test")
    log.info("upload %s", PLANTED["filename"])
    try:
        raise RuntimeError(PLANTED["bearer"])
    except RuntimeError:
        log.exception("failed with %s", PLANTED["jwt"])
    text = json.dumps(logs())
    assert "Mrs Smith" not in text and "abc.def-ghi_jkl" not in text and "eyJhbGciOiJIUzI1NiJ9" not in text
    assert text.count("[redacted]") >= 3


def test_a_full_analysis_logs_no_image_or_filename(client, state, image, logs):
    process_job(state, _submit(client, image))
    text = json.dumps(logs())
    assert "wound.png" not in text and "iVBORw0KGgo" not in text and "\\x89PNG" not in text


# -------------------------------------------- REQ-002 / REQ-004: metrics and faults
def test_injected_model_fault_is_counted_and_traces_to_one_job(client, state, image, logs, monkeypatch):
    def broken(*args, **kwargs):
        raise ApiError("MODEL_FAILURE", "INFERENCE_FAILED", "The model failed")

    monkeypatch.setattr(tasks, "analyse_and_store", broken)
    before = _sample("dfu_errors_total", failure_class="MODEL", category="MODEL_FAILURE", source="worker")
    analysis_id = _submit(client, image)
    assert process_job(state, analysis_id).status == FAILED
    assert _sample("dfu_errors_total", failure_class="MODEL", category="MODEL_FAILURE", source="worker") == before + 1
    traced = {line.get("analysis_id") for line in logs() if line.get("request_id") == TRACE and "analysis_id" in line}
    assert traced == {analysis_id}


def test_quality_rejection_is_an_outcome_not_an_error(client, state, make_image, held):
    errors_before = sum(s.value for s in m.ERRORS.collect()[0].samples if s.name == "dfu_errors_total")
    rejected_before = _sample("dfu_analyses_total", outcome=QUALITY_REJECTED)
    analysis_id = _submit(client, make_image(size=(96, 80)).read_bytes())
    import asyncio

    assert asyncio.run(run_job(state, held, analysis_id)).status == QUALITY_REJECTED
    assert _sample("dfu_analyses_total", outcome=QUALITY_REJECTED) == rejected_before + 1
    assert _sample("dfu_job_duration_seconds_count", outcome=QUALITY_REJECTED) >= 1
    assert sum(s.value for s in m.ERRORS.collect()[0].samples if s.name == "dfu_errors_total") == errors_before


def test_client_errors_count_under_their_failure_class(client):
    before = _sample("dfu_errors_total", failure_class="INPUT", category="NOT_FOUND", source="api")
    client.get("/api/v2/analyses/ana_missing")
    assert _sample("dfu_errors_total", failure_class="INPUT", category="NOT_FOUND", source="api") == before + 1


def test_metrics_endpoint_reports_the_required_series(client, held):
    held.waiting, held.model = 7, "tiny-test-model"
    client.get("/health/live")
    body = client.get("/metrics").text
    for name in ("dfu_http_requests_total", "dfu_http_request_duration_seconds", "dfu_errors_total",
                 "dfu_queue_depth 7.0", "dfu_job_duration_seconds", "dfu_analyses_total", "dfu_model_ready 1.0"):
        assert name in body
    assert 'route="/health/live"' in body
    held.model = None
    assert "dfu_model_ready 0.0" in client.get("/metrics").text


def test_metrics_labels_never_carry_ids(client, state, image):
    process_job(state, _submit(client, image))
    body = client.get("/metrics").text
    assert "ana_" not in body and "upl_" not in body and TRACE not in body


def test_metrics_are_private(settings, tiny_engine, auth, held):
    app = create_app(settings, engine=tiny_engine, verifier=auth.verifier, queue=held)
    with TestClient(app, client=("93.184.216.34", 4000)) as public:
        assert public.get("/metrics").status_code == 404
    with TestClient(app, client=("10.0.0.5", 4000)) as private:
        assert private.get("/metrics").status_code == 200


def test_a_metrics_token_replaces_the_network_check(settings, tiny_engine, auth, held):
    settings.metrics_token = "scrape-secret"
    app = create_app(settings, engine=tiny_engine, verifier=auth.verifier, queue=held)
    with TestClient(app) as local:
        assert local.get("/metrics").status_code == 404
        assert local.get("/metrics", headers={"Authorization": "Bearer scrape-secret"}).status_code == 200


def test_metrics_survive_a_queue_outage(client, held):
    held.reachable = False
    assert "dfu_queue_depth -1.0" in client.get("/metrics").text


def test_broken_telemetry_never_fails_a_request(client, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("metrics backend down")

    monkeypatch.setattr(m.HTTP_REQUESTS, "labels", explode)
    monkeypatch.setattr(m.ERRORS, "labels", explode)
    assert client.get("/health/live").status_code == 200
    assert client.get("/api/v2/analyses/ana_missing").status_code == 404
