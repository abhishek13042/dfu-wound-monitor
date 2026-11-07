"""P10-S02 Locust suite for a staging deployment (REQ-P10-S02-001).

Never point this at production: every virtual user makes synthetic cases and
uploads synthetic images.  Each user needs its own staging test account, so pass
one bearer token per account (comma-separated); users take them in turn.

    DFU_LOAD_TOKENS=<token>,<token> locust -f tests/load/locustfile.py --headless \
        --host https://<staging> -u 50 -r 5 -t 10m --csv reports/final/p10_s02_staging

The mix and the flow are in ``tests/load/scenarios.py``, shared with the
single-machine driver ``scripts/evaluation/run_load_baseline.py``.
"""

from __future__ import annotations

import itertools
import os
import sys
from pathlib import Path

from locust import HttpUser, between, events, task

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.api.consent import CONSENT_VERSION  # noqa: E402
from tests.load import scenarios  # noqa: E402

_TOKENS = itertools.cycle([token.strip() for token in os.environ.get("DFU_LOAD_TOKENS", "").split(",")
                           if token.strip()] or [""])
_SEEDS = itertools.count(1)


class LocustHttp:
    """The ``scenarios.Http`` interface over Locust's client, so Locust records every request."""

    def __init__(self, user: HttpUser, token: str) -> None:
        self.client = user.client
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}

    def request(self, method, path, *, name, json=None, body=None, ok=(200,)):
        signed = path.startswith("http") or "/blobs/" in path  # a signed URL carries its own permission
        with self.client.request(method, path, name=name, json=json, data=body, catch_response=True,
                                 headers=None if signed else self.headers) as response:
            if response.status_code in ok:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")
            return response


class Patient(HttpUser):
    wait_time = between(1, 3)

    def on_start(self) -> None:
        self.http = LocustHttp(self, next(_TOKENS))
        self.state = scenarios.UserState(seed=next(_SEEDS) * 100_000)
        scenarios.start(self.http, self.state, CONSENT_VERSION)

    @task(scenarios.MIX["browse"])
    def browse(self) -> None:
        scenarios.browse(self.http, self.state)

    @task(scenarios.MIX["analyse"])
    def analyse(self) -> None:
        self.state.seed += 1
        outcome = scenarios.upload_and_analyse(self.http, self.state, scenarios.synthetic_image(self.state.seed))
        # Submit-to-result is the headline measure (spec §9), so it is a row of its own.
        events.request.fire(request_type="JOB", name=f"submit to result: {outcome.status}",
                            response_time=(outcome.submit_to_result_s or 0) * 1000, response_length=0,
                            exception=None if outcome.status in ("COMPLETED", "REJECTED_BUSY") else outcome.status,
                            context={})
