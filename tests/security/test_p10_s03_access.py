"""REQ-P10-S03-003/004: consent before upload, rate limits, security headers and CORS."""

from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.consent import CONSENT_VERSION
from src.api.limits import MAX_KEYS, RateLimiter
from src.api.service import ApiSettings


def _upload(client: TestClient, data: bytes = b"x" * 100):
    return client.post("/api/v2/uploads", json={
        "filename": "wound.png", "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})


# ------------------------------------------------------------------ consent
def test_upload_needs_consent_first(client):
    refused = _upload(client)
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "CONSENT_REQUIRED"
    assert refused.json()["error"]["details"]["text_version"] == CONSENT_VERSION
    assert client.post("/api/v2/consent", json={"text_version": CONSENT_VERSION}).status_code == 200
    assert _upload(client).status_code == 201


def test_consent_reports_the_version_and_the_time_accepted(client):
    before = client.get("/api/v2/consent").json()
    assert before == {"text_version": CONSENT_VERSION, "accepted_at": None, "retention_hours": 24}
    first = client.post("/api/v2/consent", json={"text_version": CONSENT_VERSION}).json()
    again = client.post("/api/v2/consent", json={"text_version": CONSENT_VERSION}).json()
    assert first["accepted_at"] and again["accepted_at"] == first["accepted_at"]
    assert client.get("/api/v2/consent").json()["accepted_at"] == first["accepted_at"]


def test_an_old_consent_version_is_refused(client):
    stale = client.post("/api/v2/consent", json={"text_version": "2020-01-v0"})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "CONSENT_VERSION_CHANGED"
    assert client.get("/api/v2/consent").json()["accepted_at"] is None
    assert client.post("/api/v2/consent", json={"text_version": CONSENT_VERSION, "extra": 1}).status_code == 400


def test_consent_belongs_to_one_user(client, auth):
    client.post("/api/v2/consent", json={"text_version": CONSENT_VERSION})
    other = auth.headers("user-b")
    assert client.get("/api/v2/consent", headers=other).json()["accepted_at"] is None
    assert client.post("/api/v2/uploads", headers=other, json={
        "filename": "w.png", "size_bytes": 1, "sha256": "0" * 64}).status_code == 403


def test_export_lists_consents(client):
    client.post("/api/v2/consent", json={"text_version": CONSENT_VERSION})
    consents = client.get("/api/v2/account/export").json()["consents"]
    assert [c["text_version"] for c in consents] == [CONSENT_VERSION]


# -------------------------------------------------------------- rate limits
def _app(tmp_path, tiny_engine, auth, **limits) -> TestClient:
    settings = ApiSettings(data_dir=tmp_path / "data", load_model=False, storage_backend="local", **limits)
    return TestClient(create_app(settings, engine=tiny_engine, verifier=auth.verifier), headers=auth.headers())


def test_address_limit_answers_429_with_retry_after(tmp_path, tiny_engine, auth):
    with _app(tmp_path, tiny_engine, auth, rate_limit_ip=3, rate_limit_user=0) as client:
        assert all(client.get("/api/v2/consent").status_code == 200 for _ in range(3))
        limited = client.get("/api/v2/consent")
        assert limited.status_code == 429
        assert limited.json()["error"]["code"] == "RATE_LIMITED"
        assert 1 <= int(limited.headers["Retry-After"]) <= 60
        assert limited.headers["X-Request-ID"]
        assert client.get("/health/live").status_code == 200  # health checks are never counted


def test_user_limit_counts_each_user_apart(tmp_path, tiny_engine, auth):
    with _app(tmp_path, tiny_engine, auth, rate_limit_ip=0, rate_limit_user=2) as client:
        assert [client.get("/api/v2/consent").status_code for _ in range(3)] == [200, 200, 429]
        assert client.get("/api/v2/consent", headers=auth.headers("user-b")).status_code == 200


def test_unsigned_requests_do_not_spend_the_user_limit(tmp_path, tiny_engine, auth):
    with _app(tmp_path, tiny_engine, auth, rate_limit_ip=0, rate_limit_user=1) as client:
        for _ in range(3):
            assert client.get("/api/v2/consent", headers={"Authorization": "Bearer nope"}).status_code == 401
        assert client.get("/api/v2/consent").status_code == 200


def test_window_slides_and_memory_stays_bounded():
    now = [0.0]
    limiter = RateLimiter(2, window_seconds=10, clock=lambda: now[0])
    assert limiter.check("a") is None and limiter.check("a") is None
    assert limiter.check("a") == 10
    now[0] = 10.5
    assert limiter.check("a") is None
    for index in range(MAX_KEYS + 50):
        limiter.check(f"k{index}")
    assert len(limiter._hits) == MAX_KEYS
    assert RateLimiter(0).check("a") is None


# ------------------------------------------------------------------ headers
def test_api_responses_carry_strict_headers(client):
    for path in ("/api/v2/consent", "/api/v2/missing", "/health/live"):
        headers = client.get(path).headers
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["Referrer-Policy"] == "no-referrer"
        assert headers["Strict-Transport-Security"].startswith("max-age=31536000")
        assert headers["Content-Security-Policy"] == "default-src 'none'; frame-ancestors 'none'"
        assert headers["X-Frame-Options"] == "DENY"


def test_dashboard_can_still_be_framed(tmp_path, tiny_engine):
    settings = ApiSettings(data_dir=tmp_path / "data", load_model=False, storage_backend="local")
    with TestClient(create_app(settings, engine=tiny_engine)) as client:
        page = client.get("/dashboard/")
        assert page.status_code == 200
        assert page.headers["X-Content-Type-Options"] == "nosniff"
        assert "X-Frame-Options" not in page.headers and "Content-Security-Policy" not in page.headers


def test_cors_allows_only_named_origins(tmp_path, tiny_engine, auth):
    with _app(tmp_path, tiny_engine, auth, cors_origins=("https://app.example",)) as client:
        allowed = client.options("/api/v2/consent", headers={
            "Origin": "https://app.example", "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization, Content-Type"})
        assert allowed.status_code == 200
        assert allowed.headers["Access-Control-Allow-Origin"] == "https://app.example"
        assert "Access-Control-Allow-Credentials" not in allowed.headers
        other = client.get("/api/v2/consent", headers={"Origin": "https://evil.example"})
        assert "Access-Control-Allow-Origin" not in other.headers


def test_no_cors_headers_without_configured_origins(client):
    response = client.get("/api/v2/consent", headers={"Origin": "https://app.example"})
    assert "Access-Control-Allow-Origin" not in response.headers
