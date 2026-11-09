"""P07-S05 against a real Redis and real arq workers, on the fixture model."""

from __future__ import annotations

import asyncio
import time

import pytest
from arq.worker import Worker, get_kwargs
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.service import ServiceState
from src.worker.queue import ArqQueue
from src.worker.settings import WorkerSettings
from src.worker.state import ACTIVE, COMPLETED
from tests.worker.conftest import count, submit, verified_upload

BURST = 6
BUSY_WAIT_SECONDS = 60


@pytest.fixture
def api(settings, tiny_engine, auth, redis_url):
    settings.redis_url = redis_url
    settings.max_queue_depth = 100
    with TestClient(create_app(settings, engine=tiny_engine, verifier=auth.verifier), headers=auth.headers()) as client:
        yield client


def _worker(state: ServiceState, redis_url: str) -> Worker:
    options = {**get_kwargs(WorkerSettings), "burst": True, "handle_signals": False, "poll_delay": 0.05,
               "ctx": {"state": state}}
    options["redis_settings"] = ArqQueue(redis_url).settings
    return Worker(**options)


async def _run_workers(states: list[ServiceState], redis_url: str) -> list[Worker]:
    workers = [_worker(state, redis_url) for state in states]
    await asyncio.gather(*(worker.async_run() for worker in workers))
    for worker in workers:  # Worker.close() needs SIGUSR1, which Windows does not have
        await worker.on_shutdown(worker.ctx)
        await worker.pool.aclose()
    return workers


def _work(settings, tiny_engine, redis_url: str, *, workers: int = 1) -> list[Worker]:
    settings.redis_url = redis_url
    states = [ServiceState(settings, tiny_engine) for _ in range(workers)]
    try:
        return asyncio.run(_run_workers(states, redis_url))
    finally:
        for state in states:
            state.db.close()


def _settled(client: TestClient, analysis_id: str) -> dict:
    deadline = time.monotonic() + BUSY_WAIT_SECONDS
    while time.monotonic() < deadline:
        body = client.get(f"/api/v2/analyses/{analysis_id}").json()
        if body["status"] not in ACTIVE:
            return body
        time.sleep(0.05)
    pytest.fail(f"{analysis_id} did not finish")


def test_two_workers_finish_a_burst_with_no_duplicates_or_losses(api, settings, tiny_engine, make_image, redis_url):
    ids = [submit(api, make_image(f"w{n}.png", size=(256, 200), seed=n).read_bytes()) for n in range(BURST)]
    workers = _work(settings, tiny_engine, redis_url, workers=2)
    state = api.app.state.service
    assert all(_settled(api, analysis_id)["status"] == COMPLETED for analysis_id in ids)
    assert len(set(ids)) == BURST
    assert count(state, "analyses") == BURST
    assert sum(worker.jobs_complete for worker in workers) == BURST
    assert all(worker.jobs_failed == 0 for worker in workers)
    assert all(state.db.load_job(analysis_id)["attempts"] == 1 for analysis_id in ids)


def test_submitting_twice_sends_one_message(api, settings, tiny_engine, image, redis_url):
    upload_id = verified_upload(api, image)
    first = api.post("/api/v2/analyses", json={"upload_id": upload_id}).json()
    api.post("/api/v2/analyses", json={"upload_id": upload_id})
    assert asyncio.run(_depth(redis_url)) == 1
    _work(settings, tiny_engine, redis_url)
    assert _settled(api, first["analysis_id"])["status"] == COMPLETED
    assert count(api.app.state.service, "analyses") == 1


async def _depth(redis_url: str) -> int:
    queue = ArqQueue(redis_url)
    try:
        return await queue.depth()
    finally:
        await queue.close()


def test_a_retry_is_delivered_after_its_back_off(api, settings, tiny_engine, image, redis_url, monkeypatch):
    from src.worker import tasks

    calls = []
    original = tasks.analyse_and_store

    def fails_once(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise OSError("first delivery fails")
        return original(*args, **kwargs)

    monkeypatch.setattr(tasks, "analyse_and_store", fails_once)
    monkeypatch.setattr(tasks, "BACKOFF_SECONDS", (0.1, 0.1, 0.1))
    analysis_id = submit(api, image)
    _work(settings, tiny_engine, redis_url)
    assert _settled(api, analysis_id)["status"] == COMPLETED
    assert api.app.state.service.db.load_job(analysis_id)["attempts"] == 2


def test_worker_matches_pipeline(api, settings, tiny_engine, image, redis_url):
    """REQ-P07-S05-005: the same image through both paths gives the same answer."""

    direct = api.post("/api/v1/analyses", files={"file": ("wound.png", image, "image/png")})
    assert direct.status_code == 201, direct.text
    analysis_id = submit(api, image)
    _work(settings, tiny_engine, redis_url)
    queued = _settled(api, analysis_id)
    expected, actual = direct.json(), queued
    assert actual["status"] == expected["status"] == COMPLETED
    for field in ("model_version", "quality", "measurement", "inference"):
        assert actual[field] == expected[field], field
    state = api.app.state.service
    assert _artifact_hashes(state, analysis_id) == _artifact_hashes(state, expected["analysis_id"])


def _artifact_hashes(state, analysis_id: str) -> dict[str, str]:
    with state.db.engine.connect() as connection:
        rows = connection.exec_driver_sql(
            "SELECT kind, sha256 FROM artifacts WHERE analysis_id = ?" if state.db.engine.dialect.name == "sqlite"
            else "SELECT kind, sha256 FROM artifacts WHERE analysis_id = %s", (analysis_id,)).all()
    return dict(rows)
