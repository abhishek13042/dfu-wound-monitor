"""P05-S01 API contract and P05-S03 dashboard checks, against the tiny test model."""

from __future__ import annotations

import io
import re
import warnings
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    from fastapi.testclient import TestClient

from src.api.app import DASHBOARD_DIR, ApiSettings, create_app
from src.inference.errors import ModelExecutionError

V1 = "/api/v1"


def _settings(tmp_path: Path, **kwargs) -> ApiSettings:
    return ApiSettings(data_dir=tmp_path / "runtime", load_model=False, **kwargs)


@pytest.fixture()
def client(tmp_path, tiny_engine):
    with TestClient(create_app(_settings(tmp_path), engine=tiny_engine)) as test_client:
        yield test_client


@pytest.fixture()
def good_png(make_image):
    return make_image("wound.png", size=(256, 200)).read_bytes()


def _blank_png() -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(np.full((200, 256, 3), 128, dtype=np.uint8)).save(buffer, format="PNG")
    return buffer.getvalue()


def _case_with_exam(client, captured_at="2026-01-05T09:30:00Z"):
    case = client.post(f"{V1}/cases", json={"identity_status": "VERIFIED", "data_source": "SYNTHETIC",
                                             "label": "demo"}).json()["case"]
    exam = client.post(f"{V1}/cases/{case['case_id']}/examinations",
                       json={"captured_at": captured_at, "timestamp_source": "USER_ENTERED"}).json()["examination"]
    return case, exam


def _upload(client, data: bytes, **form):
    return client.post(f"{V1}/analyses", files={"file": ("wound.png", data, "image/png")},
                       data={k: str(v) for k, v in form.items()})


def _assert_error(response, status: int, category: str, code: str | None = None):
    assert response.status_code == status, response.text
    body = response.json()
    assert body["api_version"] == "v1"
    assert body["error"]["category"] == category
    if code:
        assert body["error"]["code"] == code
    return body


# ----------------------------------------------------------------- health
def test_liveness_and_readiness(client):
    live = client.get("/health/live")
    assert live.status_code == 200 and live.json()["status"] == "ALIVE"
    ready = client.get("/health/ready").json()
    assert ready == {**ready, "status": "READY", "model": "READY", "database": "READY",
                     "model_version": "tiny-test-model"}
    assert ready["schema_version"] >= 1


def test_readiness_reports_missing_model(tmp_path):
    settings = _settings(tmp_path, inference_config=tmp_path / "missing.json")
    settings.load_model = True
    with TestClient(create_app(settings)) as client:
        assert client.get("/health/live").status_code == 200
        ready = client.get("/health/ready")
        assert ready.status_code == 503
        assert ready.json()["model"] == "NOT_READY" and ready.json()["database"] == "READY"
        _assert_error(client.get(f"{V1}/model"), 503, "MODEL_NOT_READY")
        response = client.post(f"{V1}/analyses", files={"file": ("x.png", b"123", "image/png")})
        _assert_error(response, 503, "MODEL_NOT_READY")


def test_model_info_exposes_versions_and_limitations(client):
    body = client.get(f"{V1}/model").json()
    assert body["model"]["model_version"] == "tiny-test-model"
    assert len(body["model"]["checkpoint_sha256"]) == 64
    assert body["quality_config"]["sha256"] and body["measurement_config"]["sha256"]
    assert any("Not a medical device" in item for item in body["limitations"])


# ----------------------------------------------------------------- analysis
def test_completed_analysis_contract(client, good_png):
    case, exam = _case_with_exam(client)
    response = _upload(client, good_png, examination_id=exam["examination_id"], pixels_per_mm=4)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["schema_name"] == "AnalysisResponse" and body["api_version"] == "v1"
    assert body["status"] == "COMPLETED" and body["model_version"] == "tiny-test-model"
    assert body["measurement"]["measurement_basis"] == "PHYSICALLY_CALIBRATED"
    assert body["measurement"]["calibration"]["pixels_per_mm"] == 4
    for section in ("input", "model", "preprocessing", "postprocessing", "measurement"):
        assert section in body["provenance"]
    assert body["image"]["original_filename"] == "wound.png"
    assert "Not a clinical measurement" in body["limitation"]

    stored = client.get(body["links"]["self"]).json()
    assert stored == body
    mask = Image.open(io.BytesIO(client.get(body["links"]["mask"]).content))
    assert mask.size == (256, 200)
    assert int((np.asarray(mask) > 127).sum()) == body["measurement"]["pixel"]["area_px"]
    assert client.get(body["links"]["image"]).content == good_png
    overlay = client.get(body["links"]["overlay"])
    assert overlay.headers["content-type"] == "image/png"
    assert Image.open(io.BytesIO(overlay.content)).size == (256, 200)
    assert client.get(body["links"]["probability"]).status_code == 200
    exam_view = client.get(f"{V1}/examinations/{exam['examination_id']}").json()
    assert [a["analysis_id"] for a in exam_view["analyses"]] == [body["analysis_id"]]


def test_uncalibrated_analysis_is_pixel_based(client, good_png):
    body = _upload(client, good_png).json()
    assert body["measurement"]["measurement_basis"] == "PIXEL_BASED"
    assert body["measurement"]["physical"] is None
    assert "UNCALIBRATED" in {w["code"] for w in body["measurement"]["warnings"]}


def test_analysis_is_repeatable(client, good_png):
    first, second = _upload(client, good_png).json(), _upload(client, good_png).json()
    assert first["analysis_id"] != second["analysis_id"]
    assert first["measurement"]["pixel"] == second["measurement"]["pixel"]


def test_quality_rejection_is_distinct_and_stored(client):
    _, exam = _case_with_exam(client)
    response = _upload(client, _blank_png(), examination_id=exam["examination_id"])
    body = _assert_error(response, 422, "QUALITY_REJECTED", "QUALITY_REJECTED")
    assert body["error"]["details"]["reason_codes"]
    analysis = body["analysis"]
    assert analysis["status"] == "QUALITY_REJECTED" and analysis["measurement"] is None
    assert "mask" not in analysis["links"]
    assert client.get(analysis["links"]["self"]).json()["status"] == "QUALITY_REJECTED"
    _assert_error(client.get(f"{V1}/analyses/{analysis['analysis_id']}/mask.png"), 404, "NOT_FOUND")


@pytest.mark.parametrize("payload, code", [
    (b"not an image", "INPUT_UNREADABLE"),
    (b"GIF89a" + b"\x00" * 64, None),
])
def test_invalid_images_are_input_errors(client, payload, code):
    _assert_error(_upload(client, payload), 400, "INVALID_INPUT", code)


def test_upload_size_limit(tmp_path, tiny_engine, good_png):
    with TestClient(create_app(_settings(tmp_path, max_upload_bytes=1000), engine=tiny_engine)) as client:
        _assert_error(_upload(client, good_png), 413, "INVALID_INPUT", "INPUT_TOO_LARGE")


@pytest.mark.parametrize("form", [
    {"pixels_per_mm": -2},
    {"pixels_per_mm": 3, "calibration_method": "GUESSED"},
    {"calibration_method": "USER_ENTERED"},
    {"threshold": 1.5},
    {"pixels_per_mm": "abc"},
])
def test_invalid_parameters_are_input_errors(client, good_png, form):
    _assert_error(_upload(client, good_png, **form), 400, "INVALID_INPUT")


def test_missing_file_is_input_error(client):
    _assert_error(client.post(f"{V1}/analyses", data={}), 400, "INVALID_INPUT", "REQUEST_INVALID")


def test_unknown_examination_is_not_found(client, good_png):
    _assert_error(_upload(client, good_png, examination_id="exam-missing"), 404, "NOT_FOUND")


def test_model_failure_is_stored_as_failed(tmp_path, tiny_engine, good_png, monkeypatch):
    with TestClient(create_app(_settings(tmp_path), engine=tiny_engine)) as client:
        def boom(*_, **__):
            raise ModelExecutionError("forward pass failed")

        monkeypatch.setattr(tiny_engine, "predict", boom)
        body = _assert_error(_upload(client, good_png), 500, "MODEL_FAILURE")
        assert body["analysis"]["status"] == "FAILED"
        assert client.get(body["analysis"]["links"]["self"]).json()["status"] == "FAILED"


def test_storage_failure_is_infrastructure_error(client, good_png):
    client.app.state.service.db.close()
    _assert_error(_upload(client, good_png), 503, "INFRASTRUCTURE_FAILURE")
    ready = client.get("/health/ready")
    assert ready.status_code == 503 and ready.json()["database"] == "NOT_READY"


# ----------------------------------------------------------------- records
def test_case_crud_and_validation(client):
    _assert_error(client.post(f"{V1}/cases", json={"identity_status": "MAYBE"}), 400, "INVALID_INPUT")
    _assert_error(client.post(f"{V1}/cases", json={"unexpected": 1}), 400, "INVALID_INPUT")
    _assert_error(client.post(f"{V1}/cases", json={"identity_status": "VERIFIED", "data_source": "FUSEG2021"}),
                  400, "INVALID_INPUT", "RECORD_INVALID")
    case, exam = _case_with_exam(client)
    assert [c["case_id"] for c in client.get(f"{V1}/cases").json()["cases"]] == [case["case_id"]]
    assert client.get(f"{V1}/cases/{case['case_id']}").json()["examinations"][0]["examination_id"] == \
        exam["examination_id"]
    _assert_error(client.get(f"{V1}/cases/nope"), 404, "NOT_FOUND")
    _assert_error(client.post(f"{V1}/cases/nope/examinations", json={}), 404, "NOT_FOUND")
    _assert_error(client.post(f"{V1}/cases/{case['case_id']}/examinations",
                              json={"captured_at": "2026-01-05T09:30:00"}), 400, "INVALID_INPUT")


def test_delete_case_removes_everything(client, good_png):
    case, exam = _case_with_exam(client)
    analysis = _upload(client, good_png, examination_id=exam["examination_id"]).json()
    deleted = client.delete(f"{V1}/cases/{case['case_id']}").json()["deleted"]
    assert deleted["examinations"] == 1 and deleted["analyses"] == 1 and deleted["blobs_deleted"] == 3
    _assert_error(client.get(analysis["links"]["self"]), 404, "NOT_FOUND")
    _assert_error(client.delete(f"{V1}/cases/{case['case_id']}"), 404, "NOT_FOUND")


# ----------------------------------------------------------------- longitudinal
def test_trend_and_compare_end_to_end(client, make_image):
    case, first = _case_with_exam(client, "2026-01-05T09:30:00Z")
    second = client.post(f"{V1}/cases/{case['case_id']}/examinations",
                         json={"captured_at": "2026-01-19T09:30:00Z",
                               "timestamp_source": "USER_ENTERED"}).json()["examination"]
    empty = client.post(f"{V1}/cases/{case['case_id']}/examinations", json={}).json()["examination"]
    a = _upload(client, make_image("a.png", (256, 200), seed=1).read_bytes(),
                examination_id=first["examination_id"]).json()
    b = _upload(client, make_image("b.png", (256, 200), seed=2).read_bytes(),
                examination_id=second["examination_id"]).json()

    trend = client.get(f"{V1}/cases/{case['case_id']}/trend").json()["trend"]
    assert trend["status"] == "AVAILABLE" and trend["basis"] == "PIXEL_BASED"
    assert [row["analysis_id"] for row in trend["rows"]] == [a["analysis_id"], b["analysis_id"]]
    assert trend["rows"][1]["days_since_baseline"] == 14
    assert {"examination_id": empty["examination_id"], "analysis_id": None,
            "reason_codes": ["NO_ANALYSIS"]} in trend["excluded"]
    assert "PIXEL_SCALE_NOT_CONTROLLED" in {w["code"] for w in trend["warnings"]}

    comparison = client.get(f"{V1}/compare", params={"analysis_a": b["analysis_id"],
                                                      "analysis_b": a["analysis_id"]}).json()["comparison"]
    assert comparison["status"] == "AVAILABLE"
    assert comparison["earlier"]["analysis_id"] == a["analysis_id"]
    area = comparison["metrics"]["area"]
    assert area["earlier"] == a["measurement"]["pixel"]["area_px"]
    assert area["later"] == b["measurement"]["pixel"]["area_px"]


def test_compare_unlinked_analyses_is_unavailable(client, good_png):
    a, b = _upload(client, good_png).json(), _upload(client, good_png).json()
    comparison = client.get(f"{V1}/compare", params={"analysis_a": a["analysis_id"],
                                                      "analysis_b": b["analysis_id"]}).json()["comparison"]
    assert comparison["status"] == "UNAVAILABLE"
    assert "CASE_UNKNOWN" in comparison["reason_codes"]
    _assert_error(client.get(f"{V1}/compare", params={"analysis_a": "x", "analysis_b": "y"}), 404, "NOT_FOUND")


def test_unverified_case_trend_is_unavailable(client, good_png):
    case = client.post(f"{V1}/cases", json={}).json()["case"]
    for day in ("2026-01-05", "2026-01-12"):
        exam = client.post(f"{V1}/cases/{case['case_id']}/examinations",
                           json={"captured_at": f"{day}T09:00:00Z", "timestamp_source": "USER_ENTERED"}).json()
        _upload(client, good_png, examination_id=exam["examination"]["examination_id"])
    trend = client.get(f"{V1}/cases/{case['case_id']}/trend").json()["trend"]
    assert trend["status"] != "AVAILABLE"


# ----------------------------------------------------------------- persistence across restarts
def test_records_survive_restart(tmp_path, tiny_engine, good_png):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings, engine=tiny_engine)) as client:
        analysis = _upload(client, good_png).json()
    with TestClient(create_app(settings, engine=tiny_engine)) as client:
        assert client.get(analysis["links"]["self"]).json() == analysis


# ----------------------------------------------------------------- openapi + dashboard
def test_openapi_documents_versioned_routes(client):
    paths = client.get("/openapi.json").json()["paths"]
    for route in ("/health/live", "/health/ready", f"{V1}/analyses", f"{V1}/cases", f"{V1}/compare",
                  f"{V1}/cases/{{case_id}}/trend"):
        assert route in paths


def test_dashboard_is_served_and_only_uses_the_api(client):
    assert client.get("/", follow_redirects=False).headers["location"] == "/dashboard/"
    page = client.get("/dashboard/")
    assert page.status_code == 200 and "DFU-WoundMonitor" in page.text
    source = (DASHBOARD_DIR / "index.html").read_text(encoding="utf-8")
    assert "Not a medical device" in source
    urls = set(re.findall(r"""fetch\(([^,)]+)""", source)) | set(re.findall(r"`(\$\{API\}[^`]*)`", source))
    assert urls, "dashboard makes no API calls"
    assert not re.search(r"https?://", source.split("<script>")[1]), "dashboard must not call external hosts"
    for path in re.findall(r"""["'`](/[a-z][^"'`]*)""", source.split("<script>")[1]):
        assert path.startswith(("/api/v1", "/health")), path


# ----------------------------------------------------------------- failure classes (REQ-P06-S02-003)
def test_every_error_has_a_failure_class(client, good_png, tmp_path, tiny_engine, monkeypatch):
    observed = {
        "INPUT": _upload(client, b"garbage").json(),
        "QUALITY": _upload(client, _blank_png()).json(),
    }
    assert client.get(f"{V1}/cases/nope").json()["error"]["failure_class"] == "INPUT"
    with TestClient(create_app(_settings(tmp_path / "m"), engine=tiny_engine)) as model_client:
        monkeypatch.setattr(tiny_engine, "predict", lambda *_, **__: (_ for _ in ()).throw(ModelExecutionError("x")))
        observed["MODEL"] = _upload(model_client, good_png).json()
    monkeypatch.undo()
    with TestClient(create_app(_settings(tmp_path / "s"), engine=tiny_engine),
                    raise_server_exceptions=False) as service_client:
        monkeypatch.setattr(service_client.app.state.service.gate, "evaluate",
                            lambda *_: (_ for _ in ()).throw(RuntimeError("bug")))
        observed["SERVICE"] = _upload(service_client, good_png).json()
        assert observed["SERVICE"]["error"]["code"] == "INTERNAL_ERROR"
        monkeypatch.undo()
        service_client.app.state.service.db.close()
        observed["PERSISTENCE"] = _upload(service_client, good_png).json()
    for failure_class, body in observed.items():
        assert body["error"]["failure_class"] == failure_class, body
