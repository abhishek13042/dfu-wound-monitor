"""P07-S03: pre-signed uploads, verification, and analysis without local files."""

from __future__ import annotations

import hashlib
import io
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from src.api.app import ApiSettings, create_app
from src.api.uploads import UPLOAD_URL_SECONDS
from src.storage.blobs import staging_key
from src.storage.database import NotFoundError

LIMIT = 25 * 1024 * 1024


def declared(data: bytes, filename: str = "wound.png") -> dict:
    return {"filename": filename, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


@pytest.fixture
def local(tiny_engine, tmp_path, auth):
    settings = ApiSettings(data_dir=tmp_path / "data", load_model=False, storage_backend="local")
    with TestClient(create_app(settings, engine=tiny_engine, verifier=auth.verifier), headers=auth.headers()) as client:
        yield client


@pytest.fixture
def s3(tiny_engine, tmp_path, s3_store, s3_endpoint, auth):
    settings = ApiSettings(data_dir=tmp_path / "data", load_model=False, storage_backend="s3",
                           s3_bucket=s3_store.bucket, s3_endpoint=s3_endpoint)
    with TestClient(create_app(settings, engine=tiny_engine, verifier=auth.verifier), headers=auth.headers()) as client:
        yield client


def put_local(client: TestClient, url: str, data: bytes):
    return client.put(url, content=data)


def put_s3(url: str, data: bytes) -> int:
    # urllib would otherwise label the body as a form, which the emulator tries to parse.
    request = urllib.request.Request(url, data=data, method="PUT", headers={"Content-Type": "application/octet-stream"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status


def store_of(client: TestClient):
    return client.app.state.service.blobs


def uploaded(client: TestClient, data: bytes, **fields) -> str:
    body = {**declared(data), **fields}
    created = client.post("/api/v2/uploads", json=body)
    assert created.status_code == 201
    store_of(client).write(staging_key(created.json()["upload_id"]), data)
    return created.json()["upload_id"]


def finished(client: TestClient, submitted) -> dict:
    assert submitted.status_code == 202, submitted.text
    url = submitted.json()["links"]["self"]
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        body = client.get(url).json()
        if body["status"] not in ("QUEUED", "RUNNING"):
            return body
        time.sleep(0.02)
    pytest.fail("The analysis did not finish")


def test_upload_url_limits(local):
    data = b"x" * 10
    before = datetime.now(UTC)
    response = local.post("/api/v2/uploads", json=declared(data))
    assert response.status_code == 201
    body = response.json()
    assert body["api_version"] == "v2"
    assert set(body) == {"api_version", "upload_id", "url", "expires_at"}
    expires = datetime.fromisoformat(body["expires_at"])
    assert expires - before <= timedelta(minutes=15)
    assert UPLOAD_URL_SECONDS <= 900
    query = parse_qs(urlsplit(body["url"]).query)
    assert int(query["length"][0]) == 10
    assert int(query["expires"][0]) <= (before + timedelta(minutes=15, seconds=1)).timestamp()


def test_oversized_declaration_is_refused(local):
    response = local.post("/api/v2/uploads", json={"filename": "a.png", "size_bytes": LIMIT + 1, "sha256": "a" * 64})
    assert response.status_code == 413
    assert response.json()["error"]["category"] == "INVALID_INPUT"


@pytest.mark.parametrize("body", [
    {"filename": "a.png", "size_bytes": 0, "sha256": "a" * 64},
    {"filename": "a.png", "size_bytes": 5, "sha256": "not-a-hash"},
    {"filename": "", "size_bytes": 5, "sha256": "a" * 64},
])
def test_invalid_declarations_are_refused(local, body):
    assert local.post("/api/v2/uploads", json=body).status_code == 400


def test_local_put_then_verify(local, make_image):
    data = make_image().read_bytes()
    body = local.post("/api/v2/uploads", json=declared(data)).json()
    assert put_local(local, body["url"], data).status_code == 200
    verified = local.post(f"/api/v2/uploads/{body['upload_id']}/verify")
    assert verified.status_code == 200
    assert verified.json()["status"] == "VERIFIED"
    assert verified.json()["format"] == "PNG"
    store = store_of(local)
    assert not store.exists(staging_key(body["upload_id"]))
    digest = hashlib.sha256(data).hexdigest()
    assert store.get(f"{digest[:2]}/{digest}.png") == data


def test_local_put_past_the_signed_length_is_refused(local):
    body = local.post("/api/v2/uploads", json=declared(b"12345")).json()
    response = put_local(local, body["url"], b"1234567890")
    assert response.status_code == 413
    assert not store_of(local).exists(staging_key(body["upload_id"]))


def test_tampered_signed_url_is_refused(local):
    body = local.post("/api/v2/uploads", json=declared(b"12345")).json()
    assert local.put(body["url"].replace("signature=", "signature=0"), content=b"12345").status_code == 403
    assert local.get(body["url"]).status_code == 403  # a PUT URL does not grant GET


def test_file_larger_than_declared_is_rejected_and_deleted(local):
    created = local.post("/api/v2/uploads", json=declared(b"abc")).json()
    key = staging_key(created["upload_id"])
    store_of(local).write(key, b"abcdef")
    response = local.post(f"/api/v2/uploads/{created['upload_id']}/verify")
    assert response.status_code == 413
    assert response.json()["error"]["category"] == "INVALID_INPUT"
    assert not store_of(local).exists(key)
    assert local.post(f"/api/v2/uploads/{created['upload_id']}/verify").status_code == 409


def test_hash_mismatch_is_rejected(local):
    created = local.post("/api/v2/uploads", json={"filename": "a.png", "size_bytes": 3, "sha256": "a" * 64}).json()
    store_of(local).write(staging_key(created["upload_id"]), b"abc")
    response = local.post(f"/api/v2/uploads/{created['upload_id']}/verify")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UPLOAD_HASH_MISMATCH"


def test_rejects_disguised_file(local):
    """A script named .png, with the right size and hash, is still not an image."""

    payload = b"<script>alert(1)</script>" * 4
    upload_id = uploaded(local, payload, filename="photo.png")
    response = local.post(f"/api/v2/uploads/{upload_id}/verify")
    assert response.status_code == 400
    assert response.json()["error"]["failure_class"] == "INPUT"
    assert not store_of(local).exists(staging_key(upload_id))


def test_format_comes_from_the_bytes_not_the_filename(local):
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), (200, 100, 50)).save(buffer, format="JPEG")
    upload_id = uploaded(local, buffer.getvalue(), filename="photo.png")
    assert local.post(f"/api/v2/uploads/{upload_id}/verify").json()["format"] == "JPEG"


def test_verify_before_upload_arrives_leaves_it_pending(local, auth):
    created = local.post("/api/v2/uploads", json=declared(b"abc")).json()
    response = local.post(f"/api/v2/uploads/{created['upload_id']}/verify")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "UPLOAD_NOT_RECEIVED"
    assert auth.repository(local.app.state.service).get_upload(created["upload_id"])["status"] == "PENDING"


def test_unverified_upload_never_reaches_the_model(local, make_image, monkeypatch):
    upload_id = uploaded(local, make_image().read_bytes())
    pipeline = local.app.state.service.pipeline
    monkeypatch.setattr(pipeline, "analyze", lambda *a, **k: pytest.fail("model was called"))
    response = local.post("/api/v2/analyses", json={"upload_id": upload_id})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "UPLOAD_NOT_VERIFIED"


def test_unknown_upload_is_not_found(local):
    assert local.post("/api/v2/uploads/upl-missing/verify").status_code == 404
    assert local.post("/api/v2/analyses", json={"upload_id": "upl-missing"}).status_code == 404


def _expire(client: TestClient, upload_id: str) -> None:
    from sqlalchemy import update

    from src.storage import models

    db = client.app.state.service.db
    past = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    with db._session() as session:
        session.execute(update(models.Upload).where(models.Upload.upload_id == upload_id).values(expires_at=past))


def test_abandoned_upload_expires_and_its_object_is_removed(local, make_image):
    upload_id = uploaded(local, make_image().read_bytes())
    _expire(local, upload_id)
    assert local.post(f"/api/v2/uploads/{upload_id}/verify").json()["error"]["code"] == "UPLOAD_EXPIRED"
    state = local.app.state.service
    assert state.db.expire_uploads(state.blobs) == 1
    assert not state.blobs.exists(staging_key(upload_id))
    assert local.post(f"/api/v2/uploads/{upload_id}/verify").status_code == 404


def test_expiry_keeps_a_blob_another_row_still_needs(local, make_image, auth):
    data = make_image().read_bytes()
    first, second = uploaded(local, data), uploaded(local, data)
    assert local.post(f"/api/v2/uploads/{first}/verify").status_code == 200
    assert local.post(f"/api/v2/uploads/{second}/verify").status_code == 200
    state = local.app.state.service
    key = auth.repository(state).get_upload(first)["storage_key"]
    _expire(local, first)
    state.db.expire_uploads(state.blobs)
    assert state.blobs.exists(key)
    _expire(local, second)
    state.db.expire_uploads(state.blobs)
    assert not state.blobs.exists(key)


def test_analysis_consumes_the_upload(local, make_image, auth):
    upload_id = uploaded(local, make_image().read_bytes())
    local.post(f"/api/v2/uploads/{upload_id}/verify")
    body = finished(local, local.post("/api/v2/analyses", json={"upload_id": upload_id}))
    assert body["api_version"] == "v2"
    with pytest.raises(NotFoundError):
        auth.repository(local.app.state.service).get_upload(upload_id)
    again = local.post("/api/v2/analyses", json={"upload_id": upload_id})
    assert again.status_code == 202 and again.json()["analysis_id"] == body["analysis_id"]


def test_artifact_links_are_signed_and_check_the_record_first(local, make_image):
    upload_id = uploaded(local, make_image().read_bytes())
    local.post(f"/api/v2/uploads/{upload_id}/verify")
    analysis = finished(local, local.post("/api/v2/analyses", json={"upload_id": upload_id}))
    link = local.get(f"/api/v2/analyses/{analysis['analysis_id']}/artifacts/image")
    assert link.status_code == 200
    expires = datetime.fromisoformat(link.json()["expires_at"])
    assert expires - datetime.now(UTC) <= timedelta(minutes=5)
    fetched = local.get(link.json()["url"])
    assert fetched.status_code == 200
    assert fetched.headers["content-type"] == "image/png"
    assert fetched.headers["x-content-type-options"] == "nosniff"
    assert local.get(link.json()["url"].split("?")[0]).status_code == 400  # no signature, no read
    assert local.get("/api/v2/analyses/ana-missing/artifacts/image").status_code == 404
    assert local.get(f"/api/v2/analyses/{analysis['analysis_id']}/artifacts/nope").status_code == 404


def test_no_public_access(s3, make_image):
    data = make_image().read_bytes()
    created = s3.post("/api/v2/uploads", json=declared(data)).json()
    assert put_s3(created["url"], data) == 200
    key = store_of(s3).presign(staging_key(created["upload_id"]), "GET", 60)
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(key.split("?")[0], timeout=30)
    assert error.value.code == 403
    assert s3.get("/health/ready").json()["storage"] == "READY"


def test_full_analysis_flow_keeps_no_image_on_api_disk(s3, make_image, tmp_path):
    """Acceptance: with S3 storage, the API's data directory never holds image bytes."""

    data = make_image("wound.png", (256, 200), seed=7).read_bytes()
    created = s3.post("/api/v2/uploads", json=declared(data)).json()
    assert created["url"].startswith("http")
    assert put_s3(created["url"], data) == 200
    assert s3.post(f"/api/v2/uploads/{created['upload_id']}/verify").json()["status"] == "VERIFIED"
    analysis = finished(s3, s3.post("/api/v2/analyses", json={"upload_id": created["upload_id"]}))
    assert analysis["status"] == "COMPLETED"
    link = s3.get(analysis["links"]["mask"]).json()["url"]
    with urllib.request.urlopen(link, timeout=30) as response:
        assert response.read().startswith(b"\x89PNG")
    with urllib.request.urlopen(s3.get(analysis["links"]["image"]).json()["url"], timeout=30) as response:
        assert response.read() == data
    data_dir = tmp_path / "data"
    assert [p for p in data_dir.rglob("*") if p.is_file() and "sqlite3" not in p.name] == []


def test_storage_outage_is_an_infrastructure_failure(tiny_engine, tmp_path, auth, monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-only")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-only")
    settings = ApiSettings(data_dir=tmp_path / "data", load_model=False, storage_backend="s3",
                           s3_bucket="b", s3_endpoint="http://127.0.0.1:1")
    with TestClient(create_app(settings, engine=tiny_engine, verifier=auth.verifier), headers=auth.headers()) as client:
        ready = client.get("/health/ready")
        assert ready.status_code == 503
        assert ready.json()["storage"] == "NOT_READY"
        created = client.post("/api/v2/uploads", json={"filename": "a.png", "size_bytes": 3, "sha256": "a" * 64})
        verify = client.post(f"/api/v2/uploads/{created.json()['upload_id']}/verify")
    assert verify.status_code == 503
    assert verify.json()["error"]["category"] == "INFRASTRUCTURE_FAILURE"
