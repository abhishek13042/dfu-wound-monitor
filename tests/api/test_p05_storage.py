"""P05-S02 persistence: migrations, integrity, atomicity, deletion."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from src.longitudinal.records import AnalysisRecord, CaseRecord, ExaminationRecord, ImageRecord
from src.storage.database import SCHEMA_VERSION, BlobStore, Database, NotFoundError, StorageError

T0 = datetime(2026, 1, 5, 9, 30, tzinfo=timezone.utc)
MODEL = {"model_version": "m-1", "architecture": "ResNetUNet/test", "checkpoint_sha256": "a" * 64, "inference_config_sha256": "b" * 64}


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "test.sqlite3")
    database.register_model(MODEL)
    yield database
    database.close()


@pytest.fixture()
def blobs(tmp_path):
    return BlobStore(tmp_path / "blobs")


def _completed(image: ImageRecord, area: int = 100) -> AnalysisRecord:
    return AnalysisRecord.create(
        image_id=image.image_id, examination_id=image.examination_id, status="COMPLETED",
        quality={"status": "ACCEPTED"}, model_version="m-1",
        measurement={"measurement_basis": "PIXEL_BASED", "pixel": {"area_px": area}},
        provenance={"input": {}, "model": {"model_version": "m-1"}, "preprocessing": {}, "postprocessing": {}},
    )


def _populated(db: Database, blobs: BlobStore):
    case = db.add_case(CaseRecord.create(identity_status="VERIFIED", data_source="SYNTHETIC"))
    exam = db.add_examination(ExaminationRecord.create(case_id=case.case_id, captured_at=T0,
                                                       timestamp_source="USER_ENTERED"))
    key, sha = blobs.put(b"image-bytes", ".png")
    image = ImageRecord.create(examination_id=exam.examination_id, sha256="c" * 64, format="PNG",
                               width=10, height=10, storage_key=key)
    mask_key, mask_sha = blobs.put(b"mask-bytes", ".png")
    analysis = db.save_analysis(image, _completed(image), [
        {"kind": "MASK", "storage_key": mask_key, "sha256": mask_sha, "media_type": "image/png"}])
    return case, exam, image, analysis, [key, mask_key]


def test_migrations_are_idempotent(tmp_path):
    path = tmp_path / "m.sqlite3"
    first = Database(path)
    assert first.schema_version() == SCHEMA_VERSION
    first.close()
    second = Database(path)
    assert second.migrate() == []
    assert second.schema_version() == SCHEMA_VERSION
    second.close()


def test_round_trip_of_all_record_types(db, blobs):
    case, exam, image, analysis, _ = _populated(db, blobs)
    assert db.get_case(case.case_id) == case
    assert db.get_examination(exam.examination_id) == exam
    assert db.get_image(image.image_id) == image
    assert db.get_analysis(analysis.analysis_id) == analysis
    assert db.list_examinations(case.case_id) == [exam]
    assert db.list_analyses(exam.examination_id) == [analysis]
    assert db.get_artifact(analysis.analysis_id, "MASK")["media_type"] == "image/png"
    assert db.get_model("m-1")["model_version"] == "m-1"


def test_unknown_ids_raise_not_found(db):
    for getter in (db.get_case, db.get_examination, db.get_image, db.get_analysis):
        with pytest.raises(NotFoundError):
            getter("missing-id")
    with pytest.raises(NotFoundError):
        db.get_artifact("missing-id", "MASK")


def test_foreign_keys_are_enforced(db):
    with pytest.raises(StorageError) as error:
        db.add_examination(ExaminationRecord.create(case_id="no-such-case"))
    assert error.value.code == "INTEGRITY_VIOLATION"


def test_duplicate_case_is_a_conflict(db):
    case = db.add_case(CaseRecord.create())
    with pytest.raises(StorageError) as error:
        db.add_case(case)
    assert error.value.code == "INTEGRITY_VIOLATION"


def test_failed_write_rolls_back_whole_analysis(db, blobs):
    case = db.add_case(CaseRecord.create())
    exam = db.add_examination(ExaminationRecord.create(case_id=case.case_id))
    image = ImageRecord.create(examination_id=exam.examination_id, sha256="d" * 64, format="PNG", width=4, height=4)
    bad = AnalysisRecord.create(  # unregistered model version violates the FK
        image_id=image.image_id, examination_id=exam.examination_id, status="COMPLETED",
        quality={"status": "ACCEPTED"}, model_version="unregistered",
        measurement={"measurement_basis": "PIXEL_BASED"},
        provenance={"input": {}, "model": {}, "preprocessing": {}, "postprocessing": {}})
    with pytest.raises(StorageError):
        db.save_analysis(image, bad, [])
    with pytest.raises(NotFoundError):
        db.get_image(image.image_id)
    assert db.list_analyses(exam.examination_id) == []


def test_mismatched_image_and_analysis_rejected(db):
    image = ImageRecord.create(sha256="e" * 64, format="PNG", width=4, height=4)
    other = ImageRecord.create(sha256="f" * 64, format="PNG", width=4, height=4)
    with pytest.raises(StorageError):
        db.save_analysis(image, _completed(other), [])


def test_model_version_conflict(db):
    db.register_model(MODEL)  # idempotent
    with pytest.raises(StorageError) as error:
        db.register_model({**MODEL, "checkpoint_sha256": "9" * 64})
    assert error.value.code == "MODEL_VERSION_CONFLICT"


def test_delete_case_cascades_and_removes_blobs(db, blobs):
    case, exam, image, analysis, keys = _populated(db, blobs)
    counts = db.delete_case(case.case_id, blobs)
    assert counts == {"examinations": 1, "analyses": 1, "blobs_deleted": 2}
    for getter, key in ((db.get_case, case.case_id), (db.get_examination, exam.examination_id),
                        (db.get_image, image.image_id), (db.get_analysis, analysis.analysis_id)):
        with pytest.raises(NotFoundError):
            getter(key)
    for key in keys:
        assert not blobs.path(key).exists()


def test_shared_blob_survives_deleting_one_case(db, blobs):
    first = _populated(db, blobs)
    second = _populated(db, blobs)  # identical bytes -> identical content-addressed keys
    assert first[4] == second[4]
    assert db.delete_case(first[0].case_id, blobs)["blobs_deleted"] == 0
    assert all(blobs.path(key).exists() for key in second[4])


def test_latest_analysis_per_examination_prefers_completed(db, blobs):
    case, exam, image, completed, _ = _populated(db, blobs)
    rejected_image = ImageRecord.create(examination_id=exam.examination_id, sha256="1" * 64, format="PNG",
                                        width=4, height=4)
    db.save_analysis(rejected_image, AnalysisRecord.create(
        image_id=rejected_image.image_id, examination_id=exam.examination_id, status="QUALITY_REJECTED",
        quality={"status": "REJECTED", "reason_codes": ["BLURRY"]},
        created_at=completed.created_at + timedelta(minutes=1)), [])
    pairs = db.latest_analysis_per_examination(case.case_id)
    assert [(e.examination_id, a.analysis_id) for e, a in pairs] == [(exam.examination_id, completed.analysis_id)]


def test_blob_store_is_content_addressed_and_blocks_traversal(blobs):
    key, sha = blobs.put(b"hello", ".bin")
    assert key == f"{sha[:2]}/{sha}.bin"
    assert blobs.get(key) == b"hello"
    assert blobs.put(b"hello", ".bin") == (key, sha)
    with pytest.raises(StorageError):
        blobs.path("../outside.txt")


def test_database_constraints_exist_at_sql_level(tmp_path):
    db = Database(tmp_path / "c.sqlite3")
    raw = sqlite3.connect(db.path)
    raw.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(sqlite3.IntegrityError):
        raw.execute("INSERT INTO cases VALUES ('c1', 'BOGUS', 'SYNTHETIC', NULL, NULL, '2026-01-01', '{}')")
    raw.close()
    db.close()
