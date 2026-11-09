"""P07-S02: behaviour the repository must keep on both databases."""

from __future__ import annotations

import re
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.longitudinal.records import CaseRecord, ExaminationRecord
from src.storage.database import StorageError
from src.storage.database import database_url as normalise_url
from src.storage.repository import Repository

MODEL = {"model_version": "m-1", "architecture": "ResNetUNet/test", "checkpoint_sha256": "a" * 64,
         "inference_config_sha256": "b" * 64}


@pytest.fixture()
def repository(database_url):
    repo = Repository(database_url)
    yield repo
    repo.close()


def test_url_normalisation():
    assert normalise_url("postgres://u@h/d") == "postgresql+psycopg://u@h/d"
    assert normalise_url("postgresql://u@h/d") == "postgresql+psycopg://u@h/d"
    assert normalise_url("relative.sqlite3").startswith("sqlite:///")


def test_examinations_without_a_date_sort_first_on_every_database(repository):
    case = repository.add_case(CaseRecord.create())
    dated = repository.add_examination(ExaminationRecord.create(
        case_id=case.case_id, captured_at=datetime(2026, 1, 5, tzinfo=UTC), timestamp_source="USER_ENTERED"))
    undated = repository.add_examination(ExaminationRecord.create(case_id=case.case_id))
    assert [e.examination_id for e in repository.list_examinations(case.case_id)] == [
        undated.examination_id, dated.examination_id]


def test_concurrent_model_registration_has_one_winner(repository):
    errors = []

    def register() -> None:
        try:
            repository.register_model(MODEL)
        except StorageError as error:
            errors.append(error)

    threads = [threading.Thread(target=register) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert repository.get_model("m-1")["model_version"] == "m-1"


def test_failed_transaction_does_not_poison_the_connection(repository):
    with pytest.raises(StorageError):
        repository.add_examination(ExaminationRecord.create(case_id="no-such-case"))
    assert repository.ping()
    assert repository.add_case(CaseRecord.create()).case_id


def test_closed_repository_reports_a_storage_error(repository):
    repository.close()
    with pytest.raises(StorageError) as error:
        repository.ping()
    assert error.value.code == "DATABASE_ERROR"


def test_api_layer_contains_no_sql():
    # Bare keywords are too common in prose; these forms only appear in SQL.
    pattern = re.compile(r"\b(SELECT\s.+\sFROM|INSERT\s+INTO|DELETE\s+FROM|UPDATE\s+\w+\s+SET)\b", re.IGNORECASE)
    offenders = [str(path) for path in Path("src/api").rglob("*.py") if pattern.search(path.read_text("utf-8"))]
    assert offenders == []
