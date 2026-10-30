"""P07-S05: the job life cycle.  No Redis here: ``process_job`` is called directly."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.errors import ApiError
from src.api.service import ServiceState
from src.worker import tasks
from src.worker.queue import ArqQueue
from src.worker.state import (
    ACTIVE,
    COMPLETED,
    FAILED,
    QUALITY_REJECTED,
    QUEUED,
    RUNNING,
    TRANSITIONS,
    IllegalTransition,
)
from src.worker.tasks import BACKOFF_SECONDS, MAX_RETRIES, process_job, sweep
from tests.worker.conftest import backdate, count, submit, verified_upload

STATES = (QUEUED, RUNNING, COMPLETED, QUALITY_REJECTED, FAILED)


def _status(state, analysis_id: str) -> str:
    return state.db.load_job(analysis_id)["status"]


def _refuse_to_run(*args, **kwargs):
    pytest.fail("The model must not run here")


def test_submit_does_not_run_model(client, state, image, monkeypatch):
    monkeypatch.setattr(tasks, "analyse_and_store", _refuse_to_run)
    state.pipeline = None
    upload_id = verified_upload(client, image)
    started = time.perf_counter()
    response = client.post("/api/v2/analyses", json={"upload_id": upload_id})
    elapsed = time.perf_counter() - started
    assert response.status_code == 202, response.text
    assert elapsed < 0.5
    body = response.json()
    assert body["status"] == QUEUED
    assert client.get(body["links"]["self"]).json()["status"] == QUEUED
    assert count(state, "analyses") == 0


def test_a_finished_job_returns_the_result(client, state, image, held):
    analysis_id = submit(client, image)
    assert held.sent == [(analysis_id, 0, 0)]
    assert process_job(state, analysis_id).status == COMPLETED
    body = client.get(f"/api/v2/analyses/{analysis_id}").json()
    assert body["schema_name"] == "AnalysisResponse"
    assert body["status"] == COMPLETED and body["model_version"] == "tiny-test-model"


def test_quality_rejection_is_a_result_and_is_not_retried(client, state, make_image):
    analysis_id = submit(client, make_image(size=(96, 80)).read_bytes())
    result = process_job(state, analysis_id)
    assert result.status == QUALITY_REJECTED and result.retry_attempt is None
    assert client.get(f"/api/v2/analyses/{analysis_id}").json()["inference"] is None


def test_submitting_twice_makes_one_job(client, state, image):
    upload_id = verified_upload(client, image)
    first = client.post("/api/v2/analyses", json={"upload_id": upload_id}).json()
    second = client.post("/api/v2/analyses", json={"upload_id": upload_id}).json()
    assert first["analysis_id"] == second["analysis_id"]
    assert count(state, "analysis_jobs") == 1


def test_another_user_cannot_see_a_waiting_job(client, image, auth):
    analysis_id = submit(client, image)
    assert client.get(f"/api/v2/analyses/{analysis_id}", headers=auth.headers("someone-else")).status_code == 404


# ------------------------------------------------------------------ state machine
def test_state_machine(client, state, image):
    assert {name: set(next_states) for name, next_states in TRANSITIONS.items()} == {
        QUEUED: {RUNNING}, RUNNING: {QUEUED, COMPLETED, QUALITY_REJECTED, FAILED},
        COMPLETED: set(), QUALITY_REJECTED: set(), FAILED: set()}
    analysis_id = submit(client, image)
    for current in STATES:
        for target in STATES:
            if target not in TRANSITIONS[current]:
                with pytest.raises(IllegalTransition):
                    state.db.move_job(analysis_id, current, target)
    assert _status(state, analysis_id) == QUEUED


def test_a_job_only_moves_from_the_state_it_is_in(client, state, image):
    analysis_id = submit(client, image)
    assert state.db.move_job(analysis_id, RUNNING, COMPLETED) is False
    assert _status(state, analysis_id) == QUEUED


# ------------------------------------------------------------------ idempotency
def test_redelivery_is_idempotent(client, state, image):
    analysis_id = submit(client, image)
    assert process_job(state, analysis_id).status == COMPLETED
    assert process_job(state, analysis_id).status is None
    assert (count(state, "analyses"), count(state, "images"), count(state, "artifacts")) == (1, 1, 2)


def test_only_one_worker_can_claim_a_job(client, state, image):
    analysis_id = submit(client, image)
    barrier = threading.Barrier(8)

    def claim(_):
        barrier.wait()
        return state.db.claim_job(analysis_id)

    with ThreadPoolExecutor(8) as pool:
        wins = [job for job in pool.map(claim, range(8)) if job is not None]
    assert len(wins) == 1 and wins[0]["attempts"] == 1


def test_worker_dying_after_saving_does_not_save_twice(client, state, image, monkeypatch):
    analysis_id = submit(client, image)
    assert process_job(state, analysis_id).status == COMPLETED
    with state.db.engine.begin() as connection:  # as if the job row had not been finished
        connection.exec_driver_sql("UPDATE analysis_jobs SET status = 'QUEUED'")
    monkeypatch.setattr(tasks, "analyse_and_store", _refuse_to_run)
    assert process_job(state, analysis_id).status == COMPLETED
    assert count(state, "analyses") == 1


# ------------------------------------------------------------------ retries
def test_retry_policy(client, state, image, monkeypatch):
    calls = []

    def outage(*args, **kwargs):
        calls.append(1)
        raise ApiError("INFRASTRUCTURE_FAILURE", "STORAGE_UNAVAILABLE", "Object storage is unavailable")

    monkeypatch.setattr(tasks, "analyse_and_store", outage)
    analysis_id = submit(client, image)
    for attempt, wait in enumerate(BACKOFF_SECONDS, start=1):
        result = process_job(state, analysis_id)
        assert (result.status, result.retry_attempt, result.retry_in) == (QUEUED, attempt, wait)
        assert state.db.load_job(analysis_id)["error"]["code"] == "STORAGE_UNAVAILABLE"
    assert MAX_RETRIES == len(BACKOFF_SECONDS)
    assert process_job(state, analysis_id).status == FAILED
    assert len(calls) == 1 + MAX_RETRIES
    body = client.get(f"/api/v2/analyses/{analysis_id}").json()
    assert body["status"] == FAILED and body["error"]["code"] == "STORAGE_UNAVAILABLE"
    assert process_job(state, analysis_id).status is None


def test_an_unknown_failure_counts_as_infrastructure(client, state, image, monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("disk")

    monkeypatch.setattr(tasks, "analyse_and_store", broken)
    assert process_job(state, submit(client, image)).retry_attempt == 1


@pytest.mark.parametrize("category, code", [("INVALID_INPUT", "INVALID_THRESHOLD"), ("MODEL_FAILURE", "INFERENCE_FAILED")])
def test_input_and_model_errors_do_not_retry(client, state, image, monkeypatch, category, code):
    def rejected(*args, **kwargs):
        raise ApiError(category, code, "Refused")

    monkeypatch.setattr(tasks, "analyse_and_store", rejected)
    analysis_id = submit(client, image)
    result = process_job(state, analysis_id)
    assert (result.status, result.retry_attempt) == (FAILED, None)
    assert client.get(f"/api/v2/analyses/{analysis_id}").json()["error"]["code"] == code


def test_a_failed_job_releases_its_upload(client, state, image, monkeypatch, auth):
    def rejected(*args, **kwargs):
        raise ApiError("INVALID_INPUT", "INVALID_THRESHOLD", "Refused")

    monkeypatch.setattr(tasks, "analyse_and_store", rejected)
    upload_id = verified_upload(client, image)
    key = auth.repository(state).get_upload(upload_id)["storage_key"]
    analysis_id = client.post("/api/v2/analyses", json={"upload_id": upload_id}).json()["analysis_id"]
    assert state.blobs.exists(key)
    process_job(state, analysis_id)
    state.db.expire_uploads(state.blobs)
    assert not state.blobs.exists(key)


# ------------------------------------------------------------------ the sweep
def test_a_lost_worker_is_requeued_once_and_then_failed(client, state, image):
    """Simulated by leaving a claimed row behind.  A real kill is in the smoke report."""

    analysis_id = submit(client, image)
    state.db.claim_job(analysis_id)
    backdate(state, analysis_id)
    assert sweep(state) == [(analysis_id, 1)]
    job = state.db.load_job(analysis_id)
    assert (job["status"], job["requeued"]) == (QUEUED, 1)

    state.db.claim_job(analysis_id)
    backdate(state, analysis_id)
    assert sweep(state) == []
    job = state.db.load_job(analysis_id)
    assert (job["status"], job["error"]["code"]) == (FAILED, "WORKER_LOST")


def test_a_lost_message_is_sent_again(client, state, image):
    analysis_id = submit(client, image)
    assert sweep(state) == []
    backdate(state, analysis_id)
    assert sweep(state) == [(analysis_id, 0)]
    assert _status(state, analysis_id) == QUEUED


def test_a_running_job_is_left_alone(client, state, image):
    analysis_id = submit(client, image)
    state.db.claim_job(analysis_id)
    assert sweep(state) == []
    assert _status(state, analysis_id) == RUNNING


def test_a_waiting_job_keeps_its_image_past_the_upload_expiry(client, state, image, auth):
    upload_id = verified_upload(client, image)
    key = auth.repository(state).get_upload(upload_id)["storage_key"]
    client.post("/api/v2/analyses", json={"upload_id": upload_id})
    state.db.expire_uploads(state.blobs)
    assert state.blobs.exists(key)


# ------------------------------------------------------------------ deletion during a job
def _delete_during_analysis(monkeypatch, delete):
    original = tasks.analyse_and_store

    def deleted_first(*args, **kwargs):
        delete()
        return original(*args, **kwargs)

    monkeypatch.setattr(tasks, "analyse_and_store", deleted_first)


def _stored_files(state) -> list[str]:
    root = state.settings.data_dir
    return [str(path) for path in root.rglob("*") if path.is_file() and not path.name.startswith("dfu_wound_monitor")]


def test_user_deleted_while_the_job_runs(client, state, image, monkeypatch, auth):
    analysis_id = submit(client, image)
    db = auth.repository(state)
    _delete_during_analysis(monkeypatch, lambda: db.delete_account(state.blobs))
    assert process_job(state, analysis_id).status is None
    assert count(state, "analysis_jobs") == 0
    assert count(state, "analyses") == 0
    assert _stored_files(state) == []


def test_case_deleted_while_the_job_runs(client, state, image, monkeypatch, auth):
    case_id = client.post("/api/v2/cases", json={"data_source": "SYNTHETIC"}).json()["case"]["case_id"]
    examination = client.post(f"/api/v2/cases/{case_id}/examinations", json={}).json()["examination"]["examination_id"]
    upload_id = verified_upload(client, image)
    analysis_id = client.post("/api/v2/analyses", json={"upload_id": upload_id,
                                                        "examination_id": examination}).json()["analysis_id"]
    db = auth.repository(state)
    _delete_during_analysis(monkeypatch, lambda: db.delete_case(case_id, state.blobs))
    assert process_job(state, analysis_id).status is None
    assert count(state, "analysis_jobs") == 0
    assert count(state, "analyses") == 0


# ------------------------------------------------------------------ overload and outages
def test_queue_full_says_when_to_retry(client, state, image, held):
    upload_id = verified_upload(client, image)
    held.waiting = 3
    response = client.post("/api/v2/analyses", json={"upload_id": upload_id})
    assert response.status_code == 429
    assert response.json()["error"]["category"] == "BUSY"
    assert response.headers["Retry-After"] == "30"
    assert count(state, "analysis_jobs") == 0


def test_lost_message_at_submit_leaves_no_orphan(client, state, image, held):
    upload_id = verified_upload(client, image)
    held.accepts = False
    response = client.post("/api/v2/analyses", json={"upload_id": upload_id})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "QUEUE_UNAVAILABLE"
    assert count(state, "analysis_jobs") == 0
    held.accepts = True
    assert client.post("/api/v2/analyses", json={"upload_id": upload_id}).status_code == 202


def test_redis_down_at_submit(settings, tiny_engine, auth, image):
    queue = ArqQueue("redis://127.0.0.1:1")
    with TestClient(create_app(settings, engine=tiny_engine, verifier=auth.verifier, queue=queue),
                    headers=auth.headers()) as client:
        upload_id = verified_upload(client, image)
        response = client.post("/api/v2/analyses", json={"upload_id": upload_id})
        ready = client.get("/health/ready")
        assert count(client.app.state.service, "analysis_jobs") == 0
    assert response.status_code == 503
    assert response.json()["error"]["category"] == "INFRASTRUCTURE_FAILURE"
    assert ready.status_code == 503 and ready.json()["queue"] == "NOT_READY"


def test_no_worker_means_no_jobs(client, state, image, held):
    upload_id = verified_upload(client, image)
    held.model = None
    state.pipeline = None
    response = client.post("/api/v2/analyses", json={"upload_id": upload_id})
    assert response.status_code == 503
    assert response.json()["error"]["category"] == "MODEL_NOT_READY"
    assert count(state, "analysis_jobs") == 0


# ------------------------------------------------------------------ health
def test_readiness_covers_the_queue(client, held):
    ready = client.get("/health/ready")
    assert ready.status_code == 200 and ready.json()["queue"] == "READY"
    held.reachable = False
    ready = client.get("/health/ready")
    assert ready.status_code == 503
    assert ready.json()["status"] == "NOT_READY" and ready.json()["queue"] == "NOT_READY"


def test_readiness_reports_a_missing_worker(client, state, held):
    held.model = None
    state.pipeline = None
    ready = client.get("/health/ready")
    assert ready.status_code == 503
    assert (ready.json()["model"], ready.json()["queue"]) == ("NOT_READY", "READY")


def test_model_route_works_without_a_model_in_the_api(settings, tiny_engine, auth, held):
    ServiceState(settings, tiny_engine).db.close()  # a worker registered the model
    settings.redis_url = "redis://not-used-by-the-held-queue"
    with TestClient(create_app(settings, verifier=auth.verifier, queue=held)) as client:
        response = client.get("/api/v1/model")
        ready = client.get("/health/ready").json()
    assert response.status_code == 200, response.text
    assert response.json()["model"]["model_version"] == "tiny-test-model"
    assert ready["model"] == "READY" and ready["model_version"] == "tiny-test-model"
    assert client.app.state.service.pipeline is None


def test_active_states_are_the_unfinished_ones():
    assert set(ACTIVE) == {name for name, next_states in TRANSITIONS.items() if next_states}
