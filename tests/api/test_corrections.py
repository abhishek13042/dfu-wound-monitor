"""P09-S03: corrected masks are new versions, measured by the same engine, marked in trends, shared only by choice."""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from src.api.corrections import read_mask
from src.api.errors import ApiError
from src.api.rendering import decode_mask_png
from src.measurement.engine import measure
from tests.api.test_auth import _analysis, _workspace
from tests.api.test_auth import client as client  # noqa: F401 - the fixture is used by name

SIZE = (256, 200)


def _png(mask: np.ndarray, mode: str = "L") -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(mask.astype(np.uint8) * 255).convert(mode).save(buffer, format="PNG")
    return buffer.getvalue()


def _square(top: int = 50, left: int = 60, side: int = 80) -> np.ndarray:
    mask = np.zeros((SIZE[1], SIZE[0]), dtype=bool)
    mask[top:top + side, left:left + side] = True
    return mask


def _post(client, headers, analysis_id: str, data: bytes, opt_in: bool | None = None):
    form = {} if opt_in is None else {"research_opt_in": str(opt_in).lower()}
    return client.post(f"/api/v2/analyses/{analysis_id}/corrections", headers=headers,
                       files={"file": ("mask.png", data, "image/png")}, data=form)


def test_original_is_immutable(client, auth, make_image):
    headers = auth.headers("corrector")
    ids = _workspace(client, headers, make_image(size=SIZE).read_bytes())
    analysis_id = ids["analysis_id"]
    before = client.get(f"/api/v2/analyses/{analysis_id}", headers=headers).json()
    mask_before = client.get(f"/api/v2/analyses/{analysis_id}/artifacts/mask", headers=headers).json()["url"]

    first = _post(client, headers, analysis_id, _png(_square()))
    second = _post(client, headers, analysis_id, _png(_square(side=40)))
    assert first.status_code == 201, first.text
    assert [first.json()["version"], second.json()["version"]] == [1, 2]
    assert first.json()["author"] == second.json()["author"]
    assert first.json()["created_at"]

    after = client.get(f"/api/v2/analyses/{analysis_id}", headers=headers).json()
    assert after == before
    state = client.app.state.service
    db = auth.repository(state, "corrector")
    original = decode_mask_png(state.blobs.get(db.get_artifact(analysis_id, "MASK")["storage_key"]))
    assert not np.array_equal(original.astype(bool), _square())
    listed = client.get(f"/api/v2/analyses/{analysis_id}/corrections", headers=headers).json()["corrections"]
    assert [row["version"] for row in listed] == [1, 2]
    assert client.get(f"/api/v2/analyses/{analysis_id}/artifacts/mask", headers=headers).status_code == 200
    assert mask_before


def test_measurements_from_corrected_mask(client, auth, make_image):
    headers = auth.headers("corrector")
    analysis_id = _workspace(client, headers, make_image(size=SIZE, seed=5).read_bytes())["analysis_id"]
    mask = _square()
    response = _post(client, headers, analysis_id, _png(mask))
    assert response.status_code == 201, response.text
    measured = response.json()["measurement"]
    expected = measure(mask.astype(np.uint8)).to_dict()
    assert measured["pixel"] == expected["pixel"]
    assert measured["status"] == "MEASURED" and measured["pixel"]["area_px"] == 80 * 80
    assert measured["provenance"]["mask_source"] == "CORRECTED"
    codes = [w["code"] for w in measured["warnings"]]
    assert "CORRECTED_MASK" in codes and "CONFIDENCE_NOT_ASSESSED" not in codes

    stored = client.get(response.json()["links"]["mask"], headers=headers)
    assert stored.status_code == 200
    blob = client.get(stored.json()["url"])
    assert np.array_equal(decode_mask_png(blob.content).astype(bool), mask)


def test_empty_mask_is_accepted_and_marked_empty(client, auth, make_image):
    headers = auth.headers("corrector")
    analysis_id = _workspace(client, headers, make_image(size=SIZE, seed=6).read_bytes())["analysis_id"]
    response = _post(client, headers, analysis_id, _png(np.zeros((SIZE[1], SIZE[0]), dtype=bool)))
    assert response.status_code == 201
    assert response.json()["measurement"]["status"] == "EMPTY"
    assert "EMPTY_MASK" in [w["code"] for w in response.json()["measurement"]["warnings"]]


def test_bad_masks_are_invalid_input(client, auth, make_image):
    headers = auth.headers("corrector")
    analysis_id = _workspace(client, headers, make_image(size=SIZE, seed=7).read_bytes())["analysis_id"]
    wrong_size = _post(client, headers, analysis_id, _png(np.zeros((10, 10), dtype=bool)))
    assert wrong_size.status_code == 400
    assert wrong_size.json()["error"]["category"] == "INVALID_INPUT"
    assert wrong_size.json()["error"]["code"] == "MASK_SIZE_MISMATCH"
    grey = np.full((SIZE[1], SIZE[0]), 128, dtype=np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(grey).save(buffer, format="PNG")
    assert _post(client, headers, analysis_id, buffer.getvalue()).json()["error"]["code"] == "MASK_VALUES"
    jpeg = io.BytesIO()
    Image.fromarray(grey).save(jpeg, format="JPEG")
    assert _post(client, headers, analysis_id, jpeg.getvalue()).json()["error"]["code"] == "MASK_NOT_PNG"
    assert _post(client, headers, analysis_id, b"not an image").json()["error"]["code"] == "MASK_NOT_PNG"
    assert client.get(f"/api/v2/analyses/{analysis_id}/corrections", headers=headers).json()["corrections"] == []


def test_read_mask_accepts_any_opaque_black_and_white_png():
    mask = _square()
    for mode in ("1", "L", "LA", "RGB", "RGBA"):  # a browser canvas writes RGBA
        assert np.array_equal(read_mask(_png(mask, mode), *SIZE), mask), mode
    tinted = np.zeros((SIZE[1], SIZE[0], 3), dtype=np.uint8)
    tinted[..., 0] = mask * 255
    buffer = io.BytesIO()
    Image.fromarray(tinted).save(buffer, format="PNG")
    with pytest.raises(ApiError) as caught:
        read_mask(buffer.getvalue(), *SIZE)
    assert caught.value.body.code == "MASK_NOT_GRAYSCALE"
    see_through = Image.fromarray(mask.astype(np.uint8) * 255).convert("RGBA")
    see_through.putalpha(128)
    buffer = io.BytesIO()
    see_through.save(buffer, format="PNG")
    with pytest.raises(ApiError) as caught:
        read_mask(buffer.getvalue(), *SIZE)
    assert caught.value.body.code == "MASK_VALUES"


def test_another_user_cannot_correct_or_read(client, auth, make_image):
    owner, other = auth.headers("corrector"), auth.headers("someone-else")
    analysis_id = _workspace(client, owner, make_image(size=SIZE, seed=8).read_bytes())["analysis_id"]
    correction = _post(client, owner, analysis_id, _png(_square())).json()
    assert _post(client, other, analysis_id, _png(_square())).status_code == 404
    assert client.get(f"/api/v2/analyses/{analysis_id}/corrections", headers=other).status_code == 404
    assert client.get(correction["links"]["mask"], headers=other).status_code == 404
    assert client.put(f"/api/v2/corrections/{correction['correction_id']}/research", headers=other,
                      json={"opt_in": True}).status_code == 404


def test_trend_marks_corrected(client, auth, make_image):
    headers = auth.headers("corrector")
    case_id = client.post("/api/v2/cases", headers=headers,
                          json={"identity_status": "VERIFIED", "data_source": "SYNTHETIC"}).json()["case"]["case_id"]
    analyses = []
    for seed, day in ((9, "2026-01-01"), (10, "2026-02-01")):
        examination = client.post(f"/api/v2/cases/{case_id}/examinations", headers=headers,
                                  json={"captured_at": f"{day}T00:00:00Z", "timestamp_source": "USER_ENTERED"})
        assert examination.status_code == 201, examination.text
        analyses.append(_analysis(client, headers, make_image(f"{seed}.png", size=SIZE, seed=seed).read_bytes(),
                                  examination.json()["examination"]["examination_id"]))
    first, second = analyses
    ids = {"case_id": case_id, "analysis_id": first}
    correction = _post(client, headers, second, _png(_square())).json()

    trend = client.get(f"/api/v2/cases/{ids['case_id']}/trend", headers=headers).json()["trend"]
    rows = {row["analysis_id"]: row for row in trend["rows"]}
    assert trend["status"] == "AVAILABLE", trend["excluded"]
    assert rows[ids["analysis_id"]]["mask_source"] == "MODEL"
    assert rows[ids["analysis_id"]]["correction_id"] is None
    assert rows[second]["mask_source"] == "CORRECTED"
    assert rows[second]["correction_id"] == correction["correction_id"]
    assert rows[second]["values"]["area"] == 80 * 80
    # The stored analysis still carries the model's own value.
    assert client.get(f"/api/v2/analyses/{second}", headers=headers).json()["measurement"]["pixel"]["area_px"] != 80 * 80


def test_export_requires_opt_in(client, auth, make_image):
    headers = auth.headers("corrector")
    analysis_id = _workspace(client, headers, make_image(size=SIZE, seed=11).read_bytes())["analysis_id"]
    unshared = _post(client, headers, analysis_id, _png(_square())).json()
    shared = _post(client, headers, analysis_id, _png(_square(side=60)), opt_in=True).json()
    assert unshared["research_opt_in"] is False and shared["research_opt_in"] is True

    db = client.app.state.service.db
    assert [row["correction_id"] for row in db.research_corrections()] == [shared["correction_id"]]
    updated = client.put(f"/api/v2/corrections/{unshared['correction_id']}/research", headers=headers,
                         json={"opt_in": True}).json()
    assert updated["research_opt_in"] is True
    assert {row["correction_id"] for row in db.research_corrections()} == {unshared["correction_id"],
                                                                           shared["correction_id"]}
    client.put(f"/api/v2/corrections/{shared['correction_id']}/research", headers=headers, json={"opt_in": False})
    assert [row["correction_id"] for row in db.research_corrections()] == [unshared["correction_id"]]

    # The user's own export always holds all their corrections; only research use needs the choice.
    export = client.get("/api/v2/account/export", headers=headers).json()
    assert {row["correction_id"] for row in export["corrections"]} == {unshared["correction_id"],
                                                                       shared["correction_id"]}
    assert all(row["url"] for row in export["corrections"])


def test_corrections_go_with_the_case_and_the_account(client, auth, make_image):
    headers = auth.headers("corrector")
    ids = _workspace(client, headers, make_image(size=SIZE, seed=12).read_bytes())
    _post(client, headers, ids["analysis_id"], _png(_square(top=10, side=33)))
    state = client.app.state.service
    db = auth.repository(state, "corrector")
    key = db.list_corrections(ids["analysis_id"])[0]["storage_key"]
    assert state.blobs.exists(key)
    assert client.delete(f"/api/v2/cases/{ids['case_id']}", headers=headers).status_code == 200
    assert not state.blobs.exists(key)
    assert client.app.state.service.db.research_corrections() == []


def test_research_export_holds_only_opted_in_masks(client, auth, make_image, tmp_path):
    from scripts.data.export_corrections import export

    headers = auth.headers("corrector")
    analysis_id = _workspace(client, headers, make_image(size=SIZE, seed=13).read_bytes())["analysis_id"]
    _post(client, headers, analysis_id, _png(_square()))
    shared = _post(client, headers, analysis_id, _png(_square(side=50)), opt_in=True).json()
    state = client.app.state.service
    manifest = export(state.db, state.blobs, tmp_path)
    assert [row["correction_id"] for row in manifest["corrections"]] == [shared["correction_id"]]
    assert manifest["corrections"][0]["review_status"] == "UNREVIEWED"
    written = (tmp_path / manifest["corrections"][0]["mask"]).read_bytes()
    assert np.array_equal(decode_mask_png(written).astype(bool), _square(side=50))
