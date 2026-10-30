"""P07-S02: the SQLite importer copies everything or nothing."""

from __future__ import annotations

import sqlite3

import pytest
from sqlalchemy import func, select

from scripts.deployment.import_sqlite import ImportRefused, import_database
from src.longitudinal.records import AnalysisRecord, CaseRecord, ExaminationRecord, ImageRecord
from src.storage import models
from src.storage.database import create_database_engine
from src.storage.repository import Repository

MODEL = {"model_version": "m-1", "architecture": "ResNetUNet/test", "checkpoint_sha256": "a" * 64,
         "inference_config_sha256": "b" * 64}


@pytest.fixture()
def source(tmp_path):
    path = tmp_path / "source.sqlite3"
    repository = Repository(path)
    repository.register_model(MODEL)
    case = repository.add_case(CaseRecord.create(data_source="SYNTHETIC"))
    examination = repository.add_examination(ExaminationRecord.create(case_id=case.case_id))
    image = ImageRecord.create(examination_id=examination.examination_id, sha256="c" * 64, format="PNG",
                               width=4, height=4)
    repository.save_analysis(image, AnalysisRecord.create(
        image_id=image.image_id, examination_id=examination.examination_id, status="COMPLETED",
        quality={"status": "ACCEPTED"}, model_version="m-1", measurement={"measurement_basis": "PIXEL_BASED"},
        provenance={"input": {}, "model": {}, "preprocessing": {}, "postprocessing": {}},
    ), [{"kind": "MASK", "storage_key": "k", "sha256": "d" * 64, "media_type": "image/png"}])
    repository.close()
    return path


def _target_counts(url: str) -> dict[str, int]:
    engine = create_database_engine(url)
    with engine.connect() as connection:
        counts = {table.name: connection.scalar(select(func.count()).select_from(table))
                  for table in models.Base.metadata.sorted_tables}
    engine.dispose()
    return counts


@pytest.fixture()
def target(database_url, tmp_path):
    return database_url if "postgresql" in database_url else str(tmp_path / "target.sqlite3")


def test_import_verifies_counts(source, target):
    report = import_database(source, target)
    assert {name: entry["rows"] for name, entry in report.items()} == {
        "users": 0, "model_versions": 1, "cases": 1, "examinations": 1, "images": 1, "analyses": 1, "artifacts": 1}
    assert _target_counts(target) == {**{name: 1 for name in report}, "uploads": 0, "analysis_jobs": 0}  # users: the demo row


def test_corrupt_source_row_aborts_with_nothing_written(source, target):
    raw = sqlite3.connect(source)
    raw.execute("UPDATE cases SET record_json = '{not json'")
    raw.commit()
    raw.close()
    with pytest.raises(ImportRefused, match="cases row 1"):
        import_database(source, target)
    Repository(target).close()  # creates the SQLite schema so the check below can run
    assert sum(_target_counts(target).values()) == 1  # only the demo user


def test_non_empty_target_is_refused(source, target):
    import_database(source, target)
    with pytest.raises(ImportRefused, match="not empty"):
        import_database(source, target)
    assert _target_counts(target)["cases"] == 1
