"""P06-S03 release smoke test.

Checks a running service (``--url``) or, by default, an in-process app built
from a fresh, empty data directory (so migrations run from scratch):

1. ``/health/live`` answers 200 (service up);
2. ``/health/ready`` answers 200 with model and database READY and the
   expected model version (model readiness is reported separately);
3. ``/api/v1/model`` reports the checkpoint SHA-256 pinned in the config;
4. a held-out image is analysed end to end and its mask artifact is served;
5. a blank image is rejected with ``QUALITY_REJECTED`` (not a model error).

Exit code 0 means every check passed.  Uses only the standard library on the
client side, so it also works against a remote deployment.

    python scripts/deployment/smoke_test.py
    python scripts/deployment/smoke_test.py --url http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import tempfile
import time
import uuid
import urllib.error
import urllib.request
import warnings
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_IMAGE = PROJECT_ROOT / "data/raw/FUSeg2021/source/data/Foot Ulcer Segmentation Challenge/test/images/1011.png"
Response = Tuple[int, Dict[str, Any], bytes]


def _multipart(field: str, filename: str, data: bytes) -> Tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{filename}\"\r\n"
            f"Content-Type: application/octet-stream\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def http_client(base: str) -> Callable[..., Response]:
    def request(method: str, path: str, upload: Optional[bytes] = None) -> Response:
        data, headers = None, {}
        if upload is not None:
            data, content_type = _multipart("file", "smoke.png", upload)
            headers["Content-Type"] = content_type
        req = urllib.request.Request(base.rstrip("/") + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                raw, status = response.read(), response.status
        except urllib.error.HTTPError as error:
            raw, status = error.read(), error.code
        try:
            return status, json.loads(raw), raw
        except ValueError:
            return status, {}, raw

    return request


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", help="base URL of a running service; default: in-process app")
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    args = parser.parse_args(argv)

    from src.inference.engine import DEFAULT_INFERENCE_CONFIG, InferenceConfig

    expected = InferenceConfig.load(DEFAULT_INFERENCE_CONFIG)
    results: List[Dict[str, Any]] = []

    def check(name: str, ok: bool, detail: Any = "") -> None:
        results.append({"check": name, "passed": bool(ok), "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")

    def run(call: Callable[..., Response]) -> None:
        status, body, _ = call("GET", "/health/live")
        check("liveness", status == 200 and body.get("status") == "ALIVE", body.get("service_version"))
        status, body, _ = call("GET", "/health/ready")
        check("readiness", status == 200 and body.get("model") == "READY" and body.get("database") == "READY",
              {k: body.get(k) for k in ("status", "model", "database", "schema_version")})
        check("model version", body.get("model_version") == expected.model_version, body.get("model_version"))
        status, body, _ = call("GET", "/api/v1/model")
        check("checkpoint checksum", status == 200 and body["model"]["checkpoint_sha256"] == expected.checkpoint_sha256
              and body["model"]["checksum_verified"] is True, body.get("model", {}).get("checkpoint_sha256", "")[:12])
        t = time.perf_counter()
        status, body, _ = call("POST", "/api/v1/analyses", args.image.read_bytes())
        seconds = time.perf_counter() - t
        check("analysis completes", status == 201 and body.get("status") == "COMPLETED",
              f"{seconds:.1f}s area_px={body.get('measurement', {}).get('pixel', {}).get('area_px')}")
        if status == 201:
            status, _, raw = call("GET", body["links"]["mask"])
            check("mask artifact served", status == 200 and raw[:8] == b"\x89PNG\r\n\x1a\n", f"{len(raw)} bytes")
            status, stored, _ = call("GET", body["links"]["self"])
            check("record persisted", status == 200 and stored.get("analysis_id") == body["analysis_id"])
        import numpy as np
        from PIL import Image

        buffer = io.BytesIO()
        Image.fromarray(np.full((400, 400, 3), 128, dtype=np.uint8)).save(buffer, format="PNG")
        status, body, _ = call("POST", "/api/v1/analyses", buffer.getvalue())
        check("quality rejection is distinct", status == 422 and body["error"]["failure_class"] == "QUALITY",
              body.get("error", {}).get("code"))

    if args.url:
        run(http_client(args.url))
    else:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from fastapi.testclient import TestClient

        from src.api.app import ApiSettings, create_app

        with tempfile.TemporaryDirectory() as tmp, \
                TestClient(create_app(ApiSettings(data_dir=Path(tmp)))) as client:

            def call(method: str, path: str, upload: Optional[bytes] = None) -> Response:
                files = {"file": ("smoke.png", upload, "application/octet-stream")} if upload is not None else None
                response = client.request(method, path, files=files)
                try:
                    return response.status_code, response.json(), response.content
                except ValueError:
                    return response.status_code, {}, response.content

            run(call)
    failed = [r for r in results if not r["passed"]]
    print(f"{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
