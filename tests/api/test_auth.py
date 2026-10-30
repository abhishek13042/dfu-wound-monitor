"""P07-S04: tokens, and proof that no route crosses from one user to another."""

from __future__ import annotations

import logging
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.auth import JwksCache, TokenVerifier
from src.api.errors import ApiError
from src.api.service import ApiSettings
from src.storage.blobs import staging_key
from src.storage.models import DEMO_OWNER

PUBLIC = {("GET", "/api/v2/model")}


@pytest.fixture
def client(tiny_engine, tmp_path, auth):
    settings = ApiSettings(data_dir=tmp_path / "data", load_model=False, storage_backend="local")
    with TestClient(create_app(settings, engine=tiny_engine, verifier=auth.verifier)) as test_client:
        yield test_client


def _analysis(client, headers, data: bytes, examination_id: str | None = None) -> str:
    import hashlib

    created = client.post("/api/v2/uploads", headers=headers, json={
        "filename": "wound.png", "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}).json()
    assert client.put(created["url"], content=data).status_code in (200, 204)
    upload_id = created["upload_id"]
    assert client.post(f"/api/v2/uploads/{upload_id}/verify", headers=headers).status_code == 200
    body = {"upload_id": upload_id, "examination_id": examination_id}
    response = client.post("/api/v2/analyses", headers=headers, json=body)
    assert response.status_code == 202, response.text
    url = response.json()["links"]["self"]
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if client.get(url, headers=headers).json()["status"] not in ("QUEUED", "RUNNING"):
            return response.json()["analysis_id"]
        time.sleep(0.02)
    pytest.fail("The analysis did not finish")


def _workspace(client, headers, image: bytes) -> dict[str, str]:
    case_id = client.post("/api/v2/cases", headers=headers, json={"data_source": "SYNTHETIC"}).json()["case"]["case_id"]
    examination = client.post(f"/api/v2/cases/{case_id}/examinations", headers=headers, json={}).json()
    examination_id = examination["examination"]["examination_id"]
    return {"case_id": case_id, "examination_id": examination_id,
            "analysis_id": _analysis(client, headers, image, examination_id)}


@pytest.mark.parametrize("build", [
    pytest.param(lambda a: a.token(key=rsa.generate_private_key(public_exponent=65537, key_size=2048)), id="forged"),
    pytest.param(lambda a: a.token(exp=1), id="expired"),
    pytest.param(lambda a: a.token(aud="another-app"), id="wrong-audience"),
    pytest.param(lambda a: a.token(iss="https://evil.test"), id="wrong-issuer"),
    pytest.param(lambda a: a.token(key="", algorithm="none"), id="alg-none"),
    pytest.param(lambda a: a.token(key="k" * 40, algorithm="HS256"), id="hs256"),
    pytest.param(lambda a: a.token(without=("exp",)), id="no-exp"),
    pytest.param(lambda a: a.token(without=("sub",)), id="no-sub"),
    pytest.param(lambda a: a.token(kid="unknown"), id="unknown-key"),
    pytest.param(lambda a: "not.a.token", id="garbage"),
])
def test_rejects_bad_tokens(client, auth, build):
    response = client.get("/api/v2/cases", headers={"Authorization": f"Bearer {build(auth)}"})
    assert response.status_code == 401
    assert response.json()["error"]["category"] == "UNAUTHENTICATED"
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_missing_token_and_wrong_scheme_are_refused(client):
    assert client.get("/api/v2/cases").status_code == 401
    assert client.get("/api/v2/cases", headers={"Authorization": "Basic abc"}).status_code == 401


def test_no_sign_in_configured_is_unavailable_not_open(tiny_engine, tmp_path, auth):
    settings = ApiSettings(data_dir=tmp_path / "data", load_model=False, storage_backend="local")
    with TestClient(create_app(settings, engine=tiny_engine)) as client:
        response = client.get("/api/v2/cases", headers=auth.headers())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AUTH_NOT_CONFIGURED"


def test_token_is_not_logged(client, auth, caplog):
    token = auth.token()
    with caplog.at_level(logging.DEBUG):
        client.get("/api/v2/cases", headers={"Authorization": f"Bearer {token}"})
        client.get("/api/v2/cases", headers={"Authorization": f"Bearer {token}x"})
    assert token not in caplog.text


def test_same_token_subject_is_the_same_user(client, auth):
    first = client.post("/api/v2/cases", headers=auth.headers("same"), json={"data_source": "SYNTHETIC"})
    listed = client.get("/api/v2/cases", headers=auth.headers("same")).json()["cases"]
    assert [case["case_id"] for case in listed] == [first.json()["case"]["case_id"]]


def test_subject_is_scoped_by_issuer(auth):
    keys = JwksCache("https://signin.test/jwks", lambda _: auth.jwks)
    first = TokenVerifier(auth.issuer, auth.audience, keys).subject(auth.token("shared"))
    second = TokenVerifier("https://other.test", auth.audience, keys).subject(auth.token("shared", iss="https://other.test"))
    assert first != second


class _Clock:
    now = 0.0

    def __call__(self) -> float:
        return self.now


def test_jwks_refreshes_after_its_lifetime_and_survives_an_outage(auth):
    clock, calls = _Clock(), []

    def fetch(_):
        calls.append(clock.now)
        if len(calls) > 1:
            raise OSError("provider down")
        return auth.jwks

    cache = JwksCache("https://signin.test/jwks", fetch, clock)
    assert cache.key(auth.key_id) is not None
    clock.now = 1e6
    assert cache.key(auth.key_id) is not None  # an outage must not sign everyone out
    assert len(calls) == 2


def test_jwks_outage_with_no_keys_is_unavailable(auth):
    def fetch(_):
        raise OSError("provider down")

    with pytest.raises(ApiError) as caught:
        JwksCache("https://signin.test/jwks", fetch).key(auth.key_id)
    assert caught.value.status == 503


def test_unknown_key_cannot_hammer_the_provider(auth):
    calls = []

    def fetch(_):
        calls.append(1)
        return auth.jwks

    cache = JwksCache("https://signin.test/jwks", fetch, _Clock())
    for _ in range(5):
        with pytest.raises(ApiError):
            cache.key("unknown")
    assert len(calls) == 1


def test_v1_and_the_dashboard_do_not_exist_beside_real_accounts(tiny_engine, tmp_path, auth):
    settings = ApiSettings(data_dir=tmp_path / "data", load_model=False, storage_backend="local",
                           auth_issuer=auth.issuer, auth_audience=auth.audience)
    with TestClient(create_app(settings, engine=tiny_engine, verifier=auth.verifier)) as client:
        assert client.get("/api/v1/cases").status_code == 404
        assert client.get("/", follow_redirects=False).status_code == 404
        assert client.get("/dashboard/").status_code == 404
        assert client.get("/api/v2/model").status_code == 200


def test_cross_user_isolation(client, auth, make_image):
    """Every v2 route is probed.  A new route with no probe here fails the test."""

    owner, intruder = auth.headers("owner"), auth.headers("intruder")
    ids = _workspace(client, owner, make_image(size=(256, 200)).read_bytes())
    upload = client.post("/api/v2/uploads", headers=owner, json={
        "filename": "a.png", "size_bytes": 3, "sha256": "a" * 64}).json()["upload_id"]
    analysis, case, examination = ids["analysis_id"], ids["case_id"], ids["examination_id"]
    probes = {
        ("GET", "/api/v2/cases/{case_id}"): ("get", f"/api/v2/cases/{case}", {}),
        ("DELETE", "/api/v2/cases/{case_id}"): ("delete", f"/api/v2/cases/{case}", {}),
        ("POST", "/api/v2/cases/{case_id}/examinations"): ("post", f"/api/v2/cases/{case}/examinations", {"json": {}}),
        ("GET", "/api/v2/cases/{case_id}/trend"): ("get", f"/api/v2/cases/{case}/trend", {}),
        ("GET", "/api/v2/examinations/{examination_id}"): ("get", f"/api/v2/examinations/{examination}", {}),
        ("GET", "/api/v2/analyses/{analysis_id}"): ("get", f"/api/v2/analyses/{analysis}", {}),
        ("GET", "/api/v2/analyses/{analysis_id}/artifacts/{kind}"): ("get", f"/api/v2/analyses/{analysis}/artifacts/mask", {}),
        ("GET", "/api/v2/compare"): ("get", "/api/v2/compare", {"params": {"analysis_a": analysis, "analysis_b": analysis}}),
        ("POST", "/api/v2/uploads/{upload_id}/verify"): ("post", f"/api/v2/uploads/{upload}/verify", {}),
        ("POST", "/api/v2/analyses"): ("post", "/api/v2/analyses", {"json": {"upload_id": upload}}),
    }
    own_data = {("POST", "/api/v2/cases"), ("GET", "/api/v2/cases"), ("POST", "/api/v2/uploads"),
                ("GET", "/api/v2/account/export"), ("DELETE", "/api/v2/account")}
    routes = {(method.upper(), path) for path, item in client.app.openapi()["paths"].items()
              for method in item if path.startswith("/api/v2")}
    assert routes - PUBLIC == set(probes) | own_data, "add a probe for each new route"

    for method, path in sorted(routes - PUBLIC):
        call, url, kwargs = probes.get((method, path), (method.lower(), path, {}))
        request = getattr(client, call)
        if call in ("post",):
            kwargs = {"json": {}, **kwargs}
        assert request(url, **kwargs).status_code == 401, (method, path)
    for key, (call, url, kwargs) in probes.items():
        response = getattr(client, call)(url, headers=intruder, **kwargs)
        assert response.status_code == 404, (key, response.text)

    assert client.get("/api/v2/cases", headers=intruder).json()["cases"] == []
    exported = client.get("/api/v2/account/export", headers=intruder).json()
    assert exported["cases"] == exported["analyses"] == exported["images"] == []
    assert client.get(f"/api/v2/cases/{case}", headers=owner).status_code == 200  # the probes changed nothing
    assert client.get(f"/api/v2/analyses/{analysis}", headers=owner).status_code == 200


def test_cannot_attach_an_analysis_to_someone_elses_examination(client, auth, make_image):
    owner, intruder = auth.headers("owner"), auth.headers("intruder")
    ids = _workspace(client, owner, make_image(size=(256, 200), seed=2).read_bytes())
    import hashlib

    data = make_image(size=(256, 200), seed=3).read_bytes()
    created = client.post("/api/v2/uploads", headers=intruder, json={
        "filename": "w.png", "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}).json()
    client.put(created["url"], content=data)
    client.post(f"/api/v2/uploads/{created['upload_id']}/verify", headers=intruder)
    response = client.post("/api/v2/analyses", headers=intruder,
                           json={"upload_id": created["upload_id"], "examination_id": ids["examination_id"]})
    assert response.status_code == 404


def test_identical_images_stay_separate_per_user(client, auth, make_image):
    data = make_image(size=(256, 200), seed=4).read_bytes()
    first = _analysis(client, auth.headers("owner"), data)
    second = _analysis(client, auth.headers("intruder"), data)
    assert client.get(f"/api/v2/analyses/{first}", headers=auth.headers("owner")).status_code == 200
    assert client.get(f"/api/v2/analyses/{second}", headers=auth.headers("intruder")).status_code == 200
    assert client.get(f"/api/v2/analyses/{second}", headers=auth.headers("owner")).status_code == 404


def test_export_contains_only_your_data_with_working_links(client, auth, make_image):
    headers = auth.headers("owner")
    ids = _workspace(client, headers, make_image(size=(256, 200), seed=5).read_bytes())
    exported = client.get("/api/v2/account/export", headers=headers).json()
    assert [case["case_id"] for case in exported["cases"]] == [ids["case_id"]]
    assert [item["analysis_id"] for item in exported["analyses"]] == [ids["analysis_id"]]
    assert exported["artifacts"] and exported["images"]
    assert client.get(exported["images"][0]["url"]).status_code == 200
    assert client.get(exported["artifacts"][0]["url"]).status_code == 200


def test_account_deletion_is_complete(client, auth, make_image):
    leaving, staying = auth.headers("leaving"), auth.headers("staying")
    shared = make_image(size=(256, 200), seed=6).read_bytes()
    ids = _workspace(client, leaving, shared)
    unique = _analysis(client, leaving, make_image(size=(256, 200), seed=7).read_bytes())
    kept = _analysis(client, staying, shared)
    pending = client.post("/api/v2/uploads", headers=leaving, json={
        "filename": "a.png", "size_bytes": 3, "sha256": "a" * 64}).json()
    client.put(pending["url"], content=b"abc")

    state = client.app.state.service
    repository = auth.repository(state, "leaving")
    exported = repository.export()
    keys = {row["storage_key"] for row in exported["artifacts"]} | {row["storage_key"] for row in exported["images"]}
    other = auth.repository(state, "staying").export()
    shared_keys = {row["storage_key"] for row in other["artifacts"]} | {row["storage_key"] for row in other["images"]}
    assert shared_keys and shared_keys < keys

    response = client.delete("/api/v2/account", headers=leaving)
    assert response.status_code == 200, response.text
    deleted = response.json()["deleted"]
    assert deleted["cases"] == 1 and deleted["analyses"] == 2 and deleted["uploads"] == 1

    assert not state.blobs.exists(staging_key(pending["upload_id"]))
    assert all(state.blobs.exists(key) for key in shared_keys)
    assert all(not state.blobs.exists(key) for key in keys - shared_keys)
    assert client.get(f"/api/v2/analyses/{kept}", headers=staying).status_code == 200

    # The next sign-in is a new, empty account, and the old ids are gone.
    assert client.get("/api/v2/cases", headers=leaving).json()["cases"] == []
    assert client.get(f"/api/v2/analyses/{unique}", headers=leaving).status_code == 404
    assert client.get(f"/api/v2/cases/{ids['case_id']}", headers=leaving).status_code == 404


def test_account_deletion_can_be_retried_after_a_storage_failure(client, auth, make_image, monkeypatch):
    headers = auth.headers("leaving")
    analysis = _analysis(client, headers, make_image(size=(256, 200), seed=8).read_bytes())
    state = client.app.state.service
    original = state.blobs.delete
    monkeypatch.setattr(state.blobs, "delete", lambda key: (_ for _ in ()).throw(OSError("storage down")))
    with pytest.raises(OSError):
        auth.repository(state, "leaving").delete_account(state.blobs)
    assert client.get(f"/api/v2/analyses/{analysis}", headers=headers).status_code == 200
    monkeypatch.setattr(state.blobs, "delete", original)
    assert client.delete("/api/v2/account", headers=headers).status_code == 200
    assert client.get(f"/api/v2/analyses/{analysis}", headers=headers).status_code == 404


def test_the_demo_workspace_is_not_an_account(client):
    from src.storage.database import StorageError

    state = client.app.state.service
    assert state.db.owner_id == DEMO_OWNER
    with pytest.raises(StorageError):
        state.db.delete_account(state.blobs)


def test_v1_data_is_invisible_to_signed_in_users(client, auth):
    created = client.post("/api/v1/cases", json={"data_source": "SYNTHETIC"}).json()["case"]["case_id"]
    assert client.get("/api/v2/cases", headers=auth.headers()).json()["cases"] == []
    assert client.get(f"/api/v2/cases/{created}", headers=auth.headers()).status_code == 404


def test_expired_signature_error_is_generic(client, auth):
    token = auth.token(exp=1)
    body = client.get("/api/v2/cases", headers={"Authorization": f"Bearer {token}"}).json()
    assert token not in str(body)
    assert jwt.__name__ not in body["error"]["message"].lower()
