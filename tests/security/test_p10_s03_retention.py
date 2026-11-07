"""REQ-P10-S03-001: images, results and uploads past DFU_RETENTION_HOURS go; kept cases stay."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from src.worker.state import COMPLETED
from src.worker.tasks import process_job, retain
from tests.worker.conftest import count, submit

LATER = datetime.now(UTC) + timedelta(hours=25)


def _keys(state) -> set[str]:
    with state.db.engine.connect() as connection:
        rows = connection.execute(text("SELECT storage_key FROM images UNION SELECT storage_key FROM artifacts"))
        return {row[0] for row in rows if row[0]}


def _finished(client, state, image, **body) -> str:
    analysis_id = submit(client, image) if not body else _submit_into(client, image, **body)
    assert process_job(state, analysis_id).status == COMPLETED
    return analysis_id


def _submit_into(client, image, examination_id: str) -> str:
    from tests.worker.conftest import verified_upload

    response = client.post("/api/v2/analyses", json={"upload_id": verified_upload(client, image),
                                                     "examination_id": examination_id})
    assert response.status_code == 202, response.text
    return response.json()["analysis_id"]


def _kept_examination(client) -> tuple[str, str]:
    case_id = client.post("/api/v2/cases", json={"label": "synthetic"}).json()["case"]["case_id"]
    examination_id = client.post(f"/api/v2/cases/{case_id}/examinations", json={}).json()["examination"]["examination_id"]
    kept = client.put(f"/api/v2/cases/{case_id}/keep", json={"keep": True})
    assert kept.status_code == 200 and kept.json()["keep"] is True
    return case_id, examination_id


def test_nothing_is_deleted_before_the_limit(client, state, image):
    _finished(client, state, image)
    counts = retain(state)
    assert counts is not None and not any(counts.values())
    assert count(state, "images") == 1


def test_old_records_and_their_objects_are_deleted(client, state, image):
    analysis_id = _finished(client, state, image)
    keys = _keys(state)
    assert keys and all(state.blobs.exists(key) for key in keys)
    counts = retain(state, LATER)
    assert counts["images"] == 1 and counts["analyses"] == 1 and counts["blobs_failed"] == 0
    for table in ("images", "analyses", "uploads", "analysis_jobs"):
        assert count(state, table) == 0, table
    assert not any(state.blobs.exists(key) for key in keys)
    assert client.get(f"/api/v2/analyses/{analysis_id}").status_code == 404
    assert state.db.retention_overdue((LATER - timedelta(hours=24)).isoformat()) == 0


def test_a_kept_case_is_left_alone(client, state, image):
    _, examination_id = _kept_examination(client)
    analysis_id = _finished(client, state, image, examination_id=examination_id)
    keys = _keys(state)
    counts = retain(state, LATER)
    assert counts["images"] == 0 and counts["analyses"] == 0
    assert count(state, "images") == 1 and count(state, "analyses") == 1
    assert all(state.blobs.exists(key) for key in keys)
    assert client.get(f"/api/v2/analyses/{analysis_id}").status_code == 200


def test_unkeeping_a_case_lets_retention_take_it(client, state, image):
    case_id, examination_id = _kept_examination(client)
    _finished(client, state, image, examination_id=examination_id)
    assert client.put(f"/api/v2/cases/{case_id}/keep", json={"keep": False}).json()["keep"] is False
    assert client.get(f"/api/v2/cases/{case_id}/keep").json()["keep"] is False
    assert retain(state, LATER)["images"] == 1


def test_a_failed_object_delete_keeps_the_rows_for_the_next_run(client, state, image, monkeypatch):
    _finished(client, state, image)
    keys = _keys(state)

    def refuse(key):
        raise OSError("storage is down")

    monkeypatch.setattr(state.blobs, "delete", refuse)
    counts = retain(state, LATER)
    assert counts["blobs_failed"] > 0 and counts["images"] == 0
    assert count(state, "images") == 1 and count(state, "analyses") == 1
    assert state.db.retention_overdue((LATER - timedelta(hours=24)).isoformat()) == 1
    monkeypatch.undo()

    counts = retain(state, LATER)
    assert counts["images"] == 1 and counts["blobs_failed"] == 0
    assert count(state, "images") == 0
    assert not any(state.blobs.exists(key) for key in keys)


def test_retention_zero_keeps_everything(client, state, image, monkeypatch):
    _finished(client, state, image)
    monkeypatch.setattr(state, "settings", replace(state.settings, retention_hours=0))
    assert retain(state, LATER) is None
    assert count(state, "images") == 1


def test_keep_routes_need_an_owned_case(client):
    assert client.get("/api/v2/cases/case_missing/keep").status_code == 404
    assert client.put("/api/v2/cases/case_missing/keep", json={"keep": True}).status_code == 404
    case_id = client.post("/api/v2/cases", json={}).json()["case"]["case_id"]
    body = client.get(f"/api/v2/cases/{case_id}/keep").json()
    assert body == {"case_id": case_id, "keep": False, "retention_hours": 24}
    assert client.put(f"/api/v2/cases/{case_id}/keep", json={"keep": "yes please"}).status_code == 400
