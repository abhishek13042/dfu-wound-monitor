"""P10-S02 load scenarios: what one virtual user does, independent of the tool that drives it.

Both drivers use these functions: ``tests/load/locustfile.py`` (Locust, for a
staging deployment) and ``scripts/evaluation/run_load_baseline.py`` (threads and
httpx, for one machine).  Each takes an ``Http`` object, so the flow is written
once and measured the same way by both.

The user mix (REQ-P10-S02-001) is stated in ``MIX``: seven in ten actions are
browsing (case list, one case, its trend, one finished analysis) and three in
ten are a full upload and analysis.  Images are synthetic, never patient photos.
"""

from __future__ import annotations

import hashlib
import io
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np
from PIL import Image

CONSENT_PATH = "/api/v2/consent"
MIX = {"browse": 7, "analyse": 3}
POLL_SECONDS = 1.0
RESULT_TIMEOUT_SECONDS = 600.0


class Http(Protocol):
    def request(self, method: str, path: str, *, name: str, json: Any = None, body: bytes | None = None,
                ok: tuple[int, ...] = (200,)) -> Any:
        """Send one request, record it under ``name``, and return the response.

        A status outside ``ok`` counts as an error for that request.
        """


@dataclass
class UserState:
    """What one virtual user has made so far, so browsing reads its own records."""

    case_id: str | None = None
    examination_id: str | None = None
    analyses: list[str] = field(default_factory=list)
    seed: int = 0


@dataclass
class Outcome:
    """How one upload-and-analyse attempt ended."""

    status: str  # COMPLETED, FAILED, REJECTED_BUSY, TIMED_OUT or ERROR
    submit_to_result_s: float | None = None
    retry_after: str | None = None


def synthetic_image(seed: int, size: tuple[int, int] = (1024, 768)) -> bytes:
    """A sharp, well-exposed synthetic wound-like PNG that passes the quality gate."""

    rng = np.random.default_rng(seed)
    width, height = size
    base = np.full((height, width, 3), (170, 120, 100), dtype=np.float32)
    yy, xx = np.mgrid[:height, :width]
    radius = min(height, width) * (0.18 + 0.1 * rng.random())
    centre = (height / 2 + rng.normal(0, height / 12), width / 2 + rng.normal(0, width / 12))
    base[((yy - centre[0]) ** 2 + (xx - centre[1]) ** 2) < radius ** 2] = (150, 40, 40)
    noisy = np.clip(base + rng.normal(0, 30, base.shape), 0, 255).astype(np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(noisy).save(buffer, format="PNG")
    return buffer.getvalue()


def start(http: Http, state: UserState, consent_version: str) -> None:
    """Accept consent and make one synthetic case with one examination."""

    http.request("POST", CONSENT_PATH, name="POST /consent", json={"text_version": consent_version})
    case = http.request("POST", "/api/v2/cases", name="POST /cases", json={"data_source": "SYNTHETIC"}, ok=(201,))
    state.case_id = case.json()["case"]["case_id"]
    examination = http.request("POST", f"/api/v2/cases/{state.case_id}/examinations", name="POST /examinations",
                               json={}, ok=(201,))
    state.examination_id = examination.json()["examination"]["examination_id"]


def browse(http: Http, state: UserState) -> None:
    """What someone reviewing their records does: the list, one case, its trend, one result."""

    http.request("GET", "/api/v2/cases", name="GET /cases")
    if state.case_id:
        http.request("GET", f"/api/v2/cases/{state.case_id}", name="GET /cases/{id}")
        http.request("GET", f"/api/v2/cases/{state.case_id}/trend", name="GET /cases/{id}/trend")
    if state.analyses:
        http.request("GET", f"/api/v2/analyses/{state.analyses[-1]}", name="GET /analyses/{id}")


def upload_and_analyse(http: Http, state: UserState, image: bytes) -> Outcome:
    """The main flow: ask for an upload URL, send the bytes, verify, submit, poll to a result."""

    created = http.request("POST", "/api/v2/uploads", name="POST /uploads", ok=(201, 200), json={
        "filename": "synthetic.png", "size_bytes": len(image), "sha256": hashlib.sha256(image).hexdigest()})
    if created.status_code not in (200, 201):
        return Outcome("ERROR")
    upload = created.json()
    http.request("PUT", upload["url"], name="PUT upload bytes", body=image, ok=(200, 204))
    http.request("POST", f"/api/v2/uploads/{upload['upload_id']}/verify", name="POST /uploads/{id}/verify")

    submitted_at = time.monotonic()
    response = http.request("POST", "/api/v2/analyses", name="POST /analyses", ok=(202, 429),
                            json={"upload_id": upload["upload_id"], "examination_id": state.examination_id})
    if response.status_code == 429:
        return Outcome("REJECTED_BUSY", retry_after=response.headers.get("Retry-After"))
    if response.status_code != 202:
        return Outcome("ERROR")
    job = response.json()
    while time.monotonic() - submitted_at < RESULT_TIMEOUT_SECONDS:
        time.sleep(POLL_SECONDS)
        polled = http.request("GET", job["links"]["self"], name="GET /analyses/{id} (poll)")
        if polled.status_code != 200:
            continue
        status = polled.json()["status"]
        if status not in ("QUEUED", "RUNNING"):
            elapsed = time.monotonic() - submitted_at
            if status == "COMPLETED":
                state.analyses.append(job["analysis_id"])
            return Outcome(status, elapsed)
    return Outcome("TIMED_OUT")
