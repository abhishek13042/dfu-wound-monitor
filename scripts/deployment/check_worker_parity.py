"""P07-S05 evidence on the real model: parity with the synchronous path, and a killed worker.

Starts a private Redis and a real ``python -m arq`` worker process, sends real
images through ``/api/v2/analyses``, and compares each result with the same image
run in this process without the queue.  It then kills a worker mid-job.

The kill is real.  The 10 minute wait for the sweep is skipped by back-dating the
row, and the report says so.  Sign-in uses the test suite's local keys.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.analysis_flow import analyse_and_store, analysis_response  # noqa: E402
from src.api.app import create_app  # noqa: E402
from src.api.service import ApiSettings, ServiceState  # noqa: E402
from src.storage.blobs import staging_key  # noqa: E402
from tests.conftest import SignIn  # noqa: E402

DEFAULT_IMAGES = "data/raw/FUSeg2021/**/test/images/*.png"
WINDOWS_REDIS = "C:/Program Files/Redis/redis-server.exe"
COMPARED = ("status", "model_version", "quality", "measurement", "inference")
START_SECONDS = 300
JOB_SECONDS = 180


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def start_worker(environment: dict[str, str], log: Path) -> subprocess.Popen:
    with log.open("ab") as stream:
        return subprocess.Popen([sys.executable, "-m", "arq", "src.worker.settings.WorkerSettings"], cwd=ROOT,
                                env=environment, stdout=stream, stderr=subprocess.STDOUT)


def wait_for(check: Any, seconds: float, what: str) -> Any:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(0.2)
    raise TimeoutError(what)


def submit(client: TestClient, data: bytes) -> str:
    created = client.post("/api/v2/uploads", json={"filename": "wound.png", "size_bytes": len(data),
                                                   "sha256": hashlib.sha256(data).hexdigest()}).json()
    upload_id = created["upload_id"]
    client.app.state.service.blobs.write(staging_key(upload_id), data)
    client.post(f"/api/v2/uploads/{upload_id}/verify").raise_for_status()
    response = client.post("/api/v2/analyses", json={"upload_id": upload_id})
    response.raise_for_status()
    return response.json()["analysis_id"]


def status_of(client: TestClient, analysis_id: str) -> dict[str, Any]:
    return client.get(f"/api/v2/analyses/{analysis_id}").json()


def settled(client: TestClient, analysis_id: str) -> dict[str, Any]:
    def finished() -> dict[str, Any] | None:
        body = status_of(client, analysis_id)
        return None if body["status"] in ("QUEUED", "RUNNING") else body

    return wait_for(finished, JOB_SECONDS, f"{analysis_id} did not finish")


def artifact_hashes(state: ServiceState, analysis_id: str) -> dict[str, str]:
    with state.db.engine.connect() as connection:
        rows = connection.execute(text("SELECT kind, sha256 FROM artifacts WHERE analysis_id = :id"),
                                  {"id": analysis_id}).all()
    return {kind: digest for kind, digest in rows}


def parity(client: TestClient, direct: ServiceState, images: list[Path]) -> list[dict[str, Any]]:
    rows = []
    for path in images:
        data = path.read_bytes()
        queued = settled(client, submit(client, data))
        stored = analyse_and_store(direct, data, filename=path.name, examination_id=None, calibration=None, threshold=None)
        expected = analysis_response(stored.record, stored.image.to_dict(), "v2").model_dump(mode="json")
        differing = [field for field in COMPARED if queued.get(field) != expected.get(field)]
        hashes = artifact_hashes(client.app.state.service, queued["analysis_id"])
        same_masks = bool(hashes) and hashes == artifact_hashes(direct, stored.record.analysis_id)
        rows.append({"image_sha256": hashlib.sha256(data).hexdigest(), "status": queued["status"],
                     "differing_fields": differing, "artifacts_compared": sorted(hashes),
                     "masks_identical": same_masks})
        print(f"{path.name}: {queued['status']} differing={differing} artifacts={sorted(hashes)} "
              f"masks_identical={same_masks}", flush=True)
    return rows


def killed_worker(client: TestClient, worker: subprocess.Popen, environment: dict[str, str], image: Path,
                  log: Path) -> tuple[dict[str, Any], subprocess.Popen]:
    state = client.app.state.service
    analysis_id = submit(client, image.read_bytes())
    wait_for(lambda: status_of(client, analysis_id)["status"] == "RUNNING", JOB_SECONDS, "The job never started")
    worker.kill()
    worker.wait(timeout=30)
    left_running = status_of(client, analysis_id)["status"] == "RUNNING"
    with state.db.engine.begin() as connection:
        connection.execute(text("UPDATE analysis_jobs SET updated_at = '2000-01-01T00:00:00+00:00' "
                                "WHERE analysis_id = :id"), {"id": analysis_id})
    replacement = start_worker(environment, log)
    body = settled(client, analysis_id)
    job = state.db.load_job(analysis_id)
    with state.db.engine.connect() as connection:
        results = connection.scalar(text("SELECT COUNT(*) FROM analyses WHERE analysis_id = :id"), {"id": analysis_id})
    return ({"worker_killed": True, "job_was_left_running": left_running, "sweep_wait_was_skipped_by_backdating": True,
             "final_status": body["status"], "attempts": job["attempts"], "requeued": job["requeued"],
             "results_stored": results}, replacement)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", default=DEFAULT_IMAGES, help="glob relative to the repo root")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/deployment/p07_s05_parity_report.json")
    args = parser.parse_args()
    images = sorted(ROOT.glob(args.images))[:args.count]
    if len(images) < args.count:
        raise SystemExit(f"Found {len(images)} images for {args.images}")
    binary = shutil.which("redis-server") or WINDOWS_REDIS
    work = Path(tempfile.mkdtemp(prefix="dfu-worker-parity-"))
    port = free_port()
    redis_url = f"redis://127.0.0.1:{port}"
    environment = {**os.environ, "DFU_DATA_DIR": str(work / "queue"), "DFU_REDIS_URL": redis_url}
    environment.pop("DFU_DATABASE_URL", None)
    log = work / "worker.log"
    redis = subprocess.Popen([binary, "--port", str(port), "--bind", "127.0.0.1", "--save", "", "--appendonly", "no"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    worker = start_worker(environment, log)
    sign_in = SignIn()
    try:
        direct = ServiceState(ApiSettings(data_dir=work / "direct", load_model=False, redis_url=None), None)
        direct.load_model()
        if direct.pipeline is None:
            raise SystemExit(f"Model did not load: {direct.model_error}")
        settings = ApiSettings(data_dir=work / "queue", load_model=False, redis_url=redis_url)
        with TestClient(create_app(settings, verifier=sign_in.verifier), headers=sign_in.headers()) as client:
            wait_for(lambda: client.get("/health/ready").status_code == 200, START_SECONDS, "The worker never got ready")
            rows = parity(client, direct, images)
            kill, worker = killed_worker(client, worker, environment, images[0], log)
            model = client.get("/health/ready").json()["model_version"]
        passed = (all(not row["differing_fields"] and row["masks_identical"] for row in rows)
                  and kill["job_was_left_running"] and kill["final_status"] == "COMPLETED"
                  and kill["attempts"] == 2 and kill["requeued"] == 1 and kill["results_stored"] == 1)
        report = {"spec": "P07-S05", "generated_at": datetime.now(UTC).isoformat(), "model_version": model,
                  "python": sys.version.split()[0], "platform": sys.platform,
                  "compared_fields": list(COMPARED) + ["mask and probability artifact SHA-256"],
                  "images": rows, "killed_worker": kill, "passed": passed}
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"passed": passed, "images": len(rows), "killed_worker": kill}, indent=2))
        return 0 if passed else 1
    finally:
        worker.kill()
        redis.kill()
        worker.wait(timeout=30)
        redis.wait(timeout=30)
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
