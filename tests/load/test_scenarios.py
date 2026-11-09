"""P10-S02: the load scenarios run end to end against the API, and overload is a 429 with a retry hint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.consent import CONSENT_VERSION
from src.api.service import ApiSettings
from tests.load import scenarios

SIZE = (256, 200)


class ClientHttp:
    """``scenarios.Http`` over the in-process test client."""

    def __init__(self, client: TestClient, headers: dict[str, str]) -> None:
        self.client, self.headers, self.calls = client, headers, []

    def request(self, method, path, *, name, json=None, body=None, ok=(200,)):
        response = self.client.request(method, path, json=json, content=body,
                                       headers=None if "/blobs/" in path else self.headers)
        self.calls.append((name, response.status_code, response.status_code in ok))
        return response


@pytest.fixture
def make_client(tiny_engine, tmp_path, auth):
    def factory(**settings) -> TestClient:
        return TestClient(create_app(ApiSettings(data_dir=tmp_path / "data", load_model=False, storage_backend="local",
                                                 **settings), engine=tiny_engine, verifier=auth.verifier))
    return factory


def test_mix_is_stated():
    assert scenarios.MIX == {"browse": 7, "analyse": 3}


def test_a_virtual_user_browses_uploads_and_gets_a_result(make_client, auth, monkeypatch):
    monkeypatch.setattr(scenarios, "POLL_SECONDS", 0.02)
    with make_client() as client:
        http = ClientHttp(client, auth.headers("load-user"))
        state = scenarios.UserState()
        scenarios.start(http, state, CONSENT_VERSION)
        outcome = scenarios.upload_and_analyse(http, state, scenarios.synthetic_image(1, SIZE))
        scenarios.browse(http, state)

    assert outcome.status == "COMPLETED" and outcome.submit_to_result_s is not None
    assert state.analyses and state.case_id
    assert all(ok for _, _, ok in http.calls), [call for call in http.calls if not call[2]]
    assert {name for name, _, _ in http.calls} >= {"POST /uploads", "PUT upload bytes", "POST /analyses",
                                                   "GET /cases/{id}/trend", "GET /analyses/{id}"}


def test_overload_is_a_429_with_retry_after(make_client, auth):
    with make_client(max_queue_depth=0) as client:
        http = ClientHttp(client, auth.headers("load-user"))
        state = scenarios.UserState()
        scenarios.start(http, state, CONSENT_VERSION)
        outcome = scenarios.upload_and_analyse(http, state, scenarios.synthetic_image(2, SIZE))

    assert outcome.status == "REJECTED_BUSY"
    assert outcome.retry_after == "30"
    assert ("POST /analyses", 429, True) in http.calls


def test_synthetic_images_differ_and_pass_as_png():
    first, second = scenarios.synthetic_image(1, SIZE), scenarios.synthetic_image(2, SIZE)
    assert first != second and first.startswith(b"\x89PNG")
