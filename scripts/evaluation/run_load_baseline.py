"""P10-S02 single-machine load baseline: step load, then an overload burst.

Starts the real API (``uvicorn src.api.app:app``) as a subprocess with its own
empty data directory, its own sign-in keys and the real segmentation model, then
drives it with ``tests/load/scenarios.py`` from threads.  Nothing touches user
data.  Jobs run on the in-process ``LocalQueue`` (one at a time), because Redis
and separate workers are not available on this machine.

    python scripts/evaluation/run_load_baseline.py --output reports/final/p10_s02_load.json

Each load level records throughput, p50/p95/p99 latency and error rate per
route, and submit-to-result time for analyses (REQ-P10-S02-002).  The overload
phase restarts the API with a small queue limit, submits a burst, and checks
that every refusal is a 429 with ``Retry-After`` and every accepted job ends
(REQ-P10-S02-004).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections import defaultdict
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import httpx
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.evaluation.run_phase_06_benchmark import hardware  # noqa: E402
from src.api.consent import CONSENT_VERSION  # noqa: E402
from tests.load import scenarios  # noqa: E402

ISSUER, AUDIENCE, KEY_ID = "https://load.test", "dfu-load", "load-key"


class SignIn:
    """One RSA key, served as a JWKS document on localhost, and token minting per virtual user."""

    def __init__(self) -> None:
        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa

        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
        document = json.dumps({"keys": [{**public, "kid": KEY_ID, "use": "sig", "alg": "RS256"}]}).encode()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 - the http.server name
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(document)

            def log_message(self, *args):  # quiet
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.jwks_url = f"http://127.0.0.1:{self.server.server_port}/jwks"

    def token(self, subject: str) -> str:
        import jwt

        now = int(time.time())
        return jwt.encode({"iss": ISSUER, "aud": AUDIENCE, "sub": subject, "iat": now, "exp": now + 3600},
                          self.key, algorithm="RS256", headers={"kid": KEY_ID})


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class Api:
    """The API under test, in its own process with its own data directory."""

    def __init__(self, sign_in: SignIn, data_dir: Path, max_queue: int, rate_limit_ip: int) -> None:
        self.port = free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        env = {**os.environ, "DFU_DATA_DIR": str(data_dir), "DFU_AUTH_ISSUER": ISSUER, "DFU_AUTH_AUDIENCE": AUDIENCE,
               "DFU_AUTH_JWKS_URL": sign_in.jwks_url, "DFU_MAX_QUEUE": str(max_queue),
               "DFU_RATE_LIMIT_IP": str(rate_limit_ip), "DFU_STORAGE_BACKEND": "local"}
        for name in ("DFU_REDIS_URL", "DFU_DATABASE_URL"):
            env.pop(name, None)
        self.log = open(data_dir / "api.log", "w", encoding="utf-8")  # noqa: SIM115 - closed in stop()
        self.process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "src.api.app:app", "--host", "127.0.0.1", "--port", str(self.port),
             "--log-level", "warning"], cwd=PROJECT_ROOT, env=env, stdout=self.log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise SystemExit(f"The API exited early; see {data_dir / 'api.log'}")
            try:
                if httpx.get(f"{self.base}/health/ready", timeout=2).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        self.stop()
        raise SystemExit("The API did not become ready within 180 s")

    def stop(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.process.kill()
        self.log.close()


class Recorder:
    """Every request as (name, started, seconds, status, ok); every analysis as an Outcome."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.requests: list[tuple[str, float, float, int, bool]] = []
        self.outcomes: list[scenarios.Outcome] = []

    def add(self, row) -> None:
        with self.lock:
            self.requests.append(row)


class DriverHttp:
    """The ``scenarios.Http`` interface over httpx, recording into a ``Recorder``."""

    def __init__(self, base: str, token: str, recorder: Recorder) -> None:
        self.client = httpx.Client(base_url=base, timeout=60)
        self.headers = {"Authorization": f"Bearer {token}"}
        self.recorder = recorder

    def request(self, method, path, *, name, json=None, body=None, ok=(200,)):
        signed = "/blobs/" in path  # a signed URL carries its own permission
        started = time.monotonic()
        try:
            response = self.client.request(method, path, json=json, content=body,
                                           headers=None if signed else self.headers)
        except httpx.HTTPError:
            self.recorder.add((name, started, time.monotonic() - started, 0, False))
            raise
        self.recorder.add((name, started, time.monotonic() - started, response.status_code,
                           response.status_code in ok))
        return response


def virtual_user(index: int, level: int, base: str, sign_in: SignIn, recorder: Recorder, stop_at: float,
                 rng: random.Random) -> None:
    http = DriverHttp(base, sign_in.token(f"load-{level}-{index}"), recorder)
    state = scenarios.UserState(seed=(level * 1000 + index) * 10_000)
    try:
        scenarios.start(http, state, CONSENT_VERSION)
        actions = [name for name, weight in scenarios.MIX.items() for _ in range(weight)]
        while time.monotonic() < stop_at:
            if rng.choice(actions) == "analyse":
                state.seed += 1
                outcome = scenarios.upload_and_analyse(http, state, scenarios.synthetic_image(state.seed))
                with recorder.lock:
                    recorder.outcomes.append(outcome)
            else:
                scenarios.browse(http, state)
            time.sleep(rng.uniform(1, 3))
    except httpx.HTTPError:
        pass  # recorded as an error row
    finally:
        http.client.close()


def percentiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"n": 0, "p50": None, "p95": None, "p99": None, "max": None}
    array = np.asarray(values)
    return {"n": len(values), "p50": round(float(np.percentile(array, 50)), 4),
            "p95": round(float(np.percentile(array, 95)), 4), "p99": round(float(np.percentile(array, 99)), 4),
            "max": round(float(array.max()), 4)}


def summarise(recorder: Recorder, users: int, duration: float) -> dict[str, Any]:
    by_name: dict[str, list[tuple]] = defaultdict(list)
    for row in recorder.requests:
        by_name[row[0]].append(row)
    rows = recorder.requests
    errors = sum(1 for row in rows if not row[4])
    outcomes = defaultdict(int)
    for outcome in recorder.outcomes:
        outcomes[outcome.status] += 1
    completed = [o.submit_to_result_s for o in recorder.outcomes if o.status == "COMPLETED"]
    return {
        "users": users, "duration_s": round(duration, 1),
        "requests": len(rows), "throughput_rps": round(len(rows) / duration, 2),
        "error_rate": round(errors / len(rows), 4) if rows else None,
        "rate_limited_429": sum(1 for row in rows if row[3] == 429 and row[0] != "POST /analyses"),
        "latency_s": percentiles([row[2] for row in rows]),
        "by_route": {name: {**percentiles([row[2] for row in group]),
                            "errors": sum(1 for row in group if not row[4])}
                     for name, group in sorted(by_name.items())},
        "analyses": {"outcomes": dict(outcomes), "completed_per_minute": round(len(completed) / duration * 60, 2),
                     "submit_to_result_s": percentiles(completed)},
    }


def run_level(base: str, sign_in: SignIn, users: int, seconds: float, seed: int) -> dict[str, Any]:
    recorder = Recorder()
    started = time.monotonic()
    stop_at = started + seconds
    threads = [threading.Thread(target=virtual_user, args=(i, users, base, sign_in, recorder, stop_at,
                                                           random.Random(seed * 100 + i)), daemon=True)
               for i in range(users)]
    for thread in threads:
        thread.start()
        time.sleep(min(0.5, seconds / max(users, 1) / 4))  # a short ramp, not a thundering start
    for thread in threads:
        thread.join()
    return summarise(recorder, users, time.monotonic() - started)


def overload(base: str, sign_in: SignIn, burst: int, max_queue: int) -> dict[str, Any]:
    """Prepare ``burst`` verified uploads, submit them all at once, then follow every accepted job to its end."""

    recorder = Recorder()
    http = DriverHttp(base, sign_in.token("overload"), recorder)
    state = scenarios.UserState()
    scenarios.start(http, state, CONSENT_VERSION)
    uploads = []
    for seed in range(burst):
        image = scenarios.synthetic_image(900_000 + seed)
        created = http.request("POST", "/api/v2/uploads", name="POST /uploads", ok=(200, 201), json={
            "filename": "synthetic.png", "size_bytes": len(image), "sha256": hashlib.sha256(image).hexdigest()}).json()
        http.request("PUT", created["url"], name="PUT upload bytes", body=image, ok=(200, 204))
        http.request("POST", f"/api/v2/uploads/{created['upload_id']}/verify", name="POST /uploads/{id}/verify")
        uploads.append(created["upload_id"])

    results: list[httpx.Response] = []
    barrier = threading.Barrier(burst)

    def submit(upload_id: str) -> None:
        client = DriverHttp(base, sign_in.token("overload"), recorder)
        barrier.wait()
        results.append(client.request("POST", "/api/v2/analyses", name="POST /analyses", ok=(202, 429),
                                      json={"upload_id": upload_id, "examination_id": state.examination_id}))
        client.client.close()

    threads = [threading.Thread(target=submit, args=(upload_id,)) for upload_id in uploads]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    accepted = [r.json() for r in results if r.status_code == 202]
    refused = [r for r in results if r.status_code == 429]
    other = [r.status_code for r in results if r.status_code not in (202, 429)]
    finals: dict[str, str] = {}
    poll_rate_limited = 0
    deadline = time.monotonic() + 600
    while len(finals) < len(accepted) and time.monotonic() < deadline:
        for job in accepted:
            if job["analysis_id"] not in finals:
                response = http.request("GET", job["links"]["self"], name="GET /analyses/{id} (poll)", ok=(200, 429))
                if response.status_code == 429:  # one user polling many jobs meets the per-user limit; wait as told
                    poll_rate_limited += 1
                    time.sleep(float(response.headers.get("Retry-After", "5")))
                    break
                status = response.json()["status"]
                if status not in ("QUEUED", "RUNNING"):
                    finals[job["analysis_id"]] = status
        time.sleep(1)
    http.client.close()
    lost = [job["analysis_id"] for job in accepted if job["analysis_id"] not in finals]
    return {
        "max_queue": max_queue, "burst": burst, "accepted_202": len(accepted), "refused_429": len(refused),
        "other_statuses": other,
        "refusals_with_retry_after": sum(1 for r in refused if r.headers.get("Retry-After")),
        "refusal_codes": sorted({r.json()["error"]["code"] for r in refused}),
        "retry_after_values": sorted({r.headers.get("Retry-After") for r in refused if r.headers.get("Retry-After")}),
        "submit_latency_s": percentiles([row[2] for row in recorder.requests if row[0] == "POST /analyses"]),
        "accepted_final_statuses": dict(sorted({s: list(finals.values()).count(s) for s in set(finals.values())}.items())),
        "accepted_jobs_lost": lost,
        "poll_rate_limited_429": poll_rate_limited,
        "passed": bool(refused) and len(refused) == sum(1 for r in refused if r.headers.get("Retry-After"))
                  and not other and not lost,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--levels", default="1,4,8,16", help="virtual users per step")
    parser.add_argument("--seconds", type=float, default=45, help="length of each step")
    parser.add_argument("--burst", type=int, default=12)
    parser.add_argument("--overload-queue", type=int, default=3)
    parser.add_argument("--rate-limit-ip", type=int, default=100_000,
                        help="every virtual user shares one IP here, so the per-IP limit is lifted")
    parser.add_argument("--seed", type=int, default=20261105)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "reports/final/p10_s02_load.json")
    args = parser.parse_args(argv)
    levels = [int(level) for level in args.levels.split(",")]

    sign_in = SignIn()
    report: dict[str, Any] = {
        "report": "P10-S02 single-machine load baseline",
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "command": "python scripts/evaluation/run_load_baseline.py " + " ".join(argv or sys.argv[1:]),
        "hardware": hardware(),
        "configuration": {
            "target": "uvicorn src.api.app:app on 127.0.0.1, one process, LocalQueue (jobs one at a time in the API "
                      "process), SQLite and local blob storage in a fresh temporary directory",
            "model": "default inference config (DFU_INFERENCE_CONFIG unset)",
            "user_mix": scenarios.MIX, "think_time_s": [1, 3], "poll_interval_s": scenarios.POLL_SECONDS,
            "image": "synthetic 1024x768 PNG, a new one per upload",
            "levels": levels, "seconds_per_level": args.seconds,
            "rate_limit_user_per_min": "default (120)", "rate_limit_ip_per_min": args.rate_limit_ip,
            "driver": "the same machine as the API, so driver and API share the CPU",
        },
        "levels": [],
    }
    with tempfile.TemporaryDirectory(prefix="dfu-load-") as temporary:
        Path(temporary, "baseline").mkdir()
        api = Api(sign_in, Path(temporary) / "baseline", 100, args.rate_limit_ip)
        try:
            for number, users in enumerate(levels):
                print(f"Level {users} users for {args.seconds:.0f} s", flush=True)
                report["levels"].append(run_level(api.base, sign_in, users, args.seconds, args.seed + number))
                level = report["levels"][-1]
                print(f"  {level['throughput_rps']} req/s, p95 {level['latency_s']['p95']} s, "
                      f"errors {level['error_rate']}, jobs {level['analyses']['outcomes']}, "
                      f"submit-to-result p50 {level['analyses']['submit_to_result_s']['p50']} s", flush=True)
        finally:
            api.stop()
        Path(temporary, "overload").mkdir()
        api = Api(sign_in, Path(temporary) / "overload", args.overload_queue, args.rate_limit_ip)
        try:
            print(f"Overload: burst of {args.burst} with a queue limit of {args.overload_queue}", flush=True)
            report["overload"] = overload(api.base, sign_in, args.burst, args.overload_queue)
            print(f"  {json.dumps(report['overload'])}", flush=True)
        finally:
            api.stop()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0 if report["overload"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
