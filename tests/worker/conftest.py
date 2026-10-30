"""Job fixtures.  ``HeldQueue`` keeps jobs waiting, so a test decides when a worker runs."""

from __future__ import annotations

import hashlib
import os
import shutil
import socket
import subprocess
import time

import pytest
from fastapi.testclient import TestClient
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import text

from src.api.app import create_app
from src.api.service import ApiSettings
from src.storage.blobs import staging_key
from src.worker.queue import QueueUnavailable

GOOD_IMAGE = (256, 200)  # passes the quality gate
WINDOWS_REDIS = "C:/Program Files/Redis/redis-server.exe"


class HeldQueue:
    def __init__(self) -> None:
        self.sent: list[tuple[str, int, float]] = []
        self.waiting = 0
        self.reachable = True
        self.accepts = True
        self.model: str | None = "tiny-test-model"

    async def enqueue(self, analysis_id: str, attempt: int = 0, defer_seconds: float = 0) -> None:
        if not self.accepts:
            raise QueueUnavailable("ConnectionError")
        self.sent.append((analysis_id, attempt, defer_seconds))

    async def depth(self) -> int:
        if not self.reachable:
            raise QueueUnavailable("ConnectionError")
        return self.waiting

    async def ping(self) -> bool:
        return self.reachable

    async def worker_model(self) -> str | None:
        return self.model

    async def close(self) -> None:
        pass


def verified_upload(client: TestClient, data: bytes, headers: dict[str, str] | None = None) -> str:
    created = client.post("/api/v2/uploads", headers=headers, json={
        "filename": "wound.png", "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    assert created.status_code == 201, created.text
    upload_id = created.json()["upload_id"]
    client.app.state.service.blobs.write(staging_key(upload_id), data)
    assert client.post(f"/api/v2/uploads/{upload_id}/verify", headers=headers).status_code == 200
    return upload_id


def submit(client: TestClient, data: bytes, headers: dict[str, str] | None = None) -> str:
    response = client.post("/api/v2/analyses", headers=headers, json={"upload_id": verified_upload(client, data, headers)})
    assert response.status_code == 202, response.text
    return response.json()["analysis_id"]


def count(state, table: str) -> int:
    with state.db.engine.connect() as connection:
        return connection.scalar(text(f"SELECT COUNT(*) FROM {table}"))


def backdate(state, analysis_id: str, when: str = "2000-01-01T00:00:00+00:00") -> None:
    with state.db.engine.begin() as connection:
        connection.execute(text("UPDATE analysis_jobs SET updated_at = :when WHERE analysis_id = :id"),
                           {"when": when, "id": analysis_id})


@pytest.fixture
def settings(tmp_path) -> ApiSettings:
    return ApiSettings(data_dir=tmp_path / "data", load_model=False, storage_backend="local", max_queue_depth=3)


@pytest.fixture
def held() -> HeldQueue:
    return HeldQueue()


@pytest.fixture
def client(settings, tiny_engine, auth, held):
    with TestClient(create_app(settings, engine=tiny_engine, verifier=auth.verifier, queue=held),
                    headers=auth.headers()) as test_client:
        yield test_client


@pytest.fixture
def state(client):
    return client.app.state.service


@pytest.fixture
def image(make_image) -> bytes:
    return make_image(size=GOOD_IMAGE).read_bytes()


@pytest.fixture(scope="session")
def redis_server():
    """A real Redis: ``DFU_TEST_REDIS_URL`` in CI, else a private local server."""

    url = os.environ.get("DFU_TEST_REDIS_URL")
    if url:
        yield url
        return
    binary = shutil.which("redis-server") or (WINDOWS_REDIS if os.path.exists(WINDOWS_REDIS) else None)
    if binary is None:
        pytest.skip("redis-server is not installed and DFU_TEST_REDIS_URL is not set")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = subprocess.Popen([binary, "--port", str(port), "--bind", "127.0.0.1", "--save", "", "--appendonly", "no"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"redis://127.0.0.1:{port}"
    ready = Redis.from_url(url)
    try:
        for _ in range(100):
            try:
                ready.ping()
                break
            except RedisConnectionError:
                time.sleep(0.05)
        yield url
    finally:
        ready.close()
        server.terminate()
        server.wait(timeout=10)


@pytest.fixture
def redis_url(redis_server):
    connection = Redis.from_url(redis_server)
    connection.flushall()
    connection.close()
    return redis_server
