"""P05-S02 persistence: SQLite records plus a content-addressed blob store.

* Separate tables and identifiers for model versions, cases, examinations,
  images, analyses and artifacts (REQ-P05-S02-001).
* Each analysis row keeps the full validated record (provenance included) and
  references the stored input image and the mask artifacts by SHA-256
  (REQ-P05-S02-002).
* Records are validated by the P04 schemas before any SQL runs.  Every
  multi-row write runs in one transaction, and foreign keys and CHECK
  constraints are enforced, so a bad write leaves nothing behind
  (REQ-P05-S02-003).
* The schema is built by ordered, idempotent migrations recorded in
  ``schema_version`` (REQ-P05-S02-004).

Retention (prototype): data are kept until ``delete_case`` is called.  That
removes the case, its examinations, images, analyses and artifact rows in one
transaction, then deletes any blob no longer referenced.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple, Union

from src.longitudinal.records import AnalysisRecord, CaseRecord, ExaminationRecord, ImageRecord

MIGRATIONS: Sequence[Tuple[int, str, str]] = (
    (1, "initial schema", """
        CREATE TABLE model_versions (
            model_version TEXT PRIMARY KEY,
            architecture TEXT NOT NULL,
            checkpoint_sha256 TEXT NOT NULL CHECK (length(checkpoint_sha256) = 64),
            inference_config_sha256 TEXT NOT NULL CHECK (length(inference_config_sha256) = 64),
            details_json TEXT NOT NULL,
            registered_at TEXT NOT NULL
        );
        CREATE TABLE cases (
            case_id TEXT PRIMARY KEY,
            identity_status TEXT NOT NULL CHECK (identity_status IN ('VERIFIED', 'UNVERIFIED', 'UNKNOWN')),
            data_source TEXT NOT NULL,
            external_reference TEXT,
            label TEXT,
            created_at TEXT NOT NULL,
            record_json TEXT NOT NULL
        );
        CREATE TABLE examinations (
            examination_id TEXT PRIMARY KEY,
            case_id TEXT REFERENCES cases(case_id) ON DELETE CASCADE,
            captured_at TEXT,
            timestamp_source TEXT NOT NULL,
            created_at TEXT NOT NULL,
            record_json TEXT NOT NULL
        );
        CREATE INDEX idx_examinations_case ON examinations(case_id, captured_at);
        CREATE TABLE images (
            image_id TEXT PRIMARY KEY,
            examination_id TEXT REFERENCES examinations(examination_id) ON DELETE CASCADE,
            sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
            storage_key TEXT,
            created_at TEXT NOT NULL,
            record_json TEXT NOT NULL
        );
        CREATE INDEX idx_images_examination ON images(examination_id);
        CREATE TABLE analyses (
            analysis_id TEXT PRIMARY KEY,
            image_id TEXT NOT NULL REFERENCES images(image_id) ON DELETE CASCADE,
            examination_id TEXT REFERENCES examinations(examination_id) ON DELETE CASCADE,
            status TEXT NOT NULL CHECK (status IN ('COMPLETED', 'QUALITY_REJECTED', 'FAILED')),
            model_version TEXT REFERENCES model_versions(model_version),
            created_at TEXT NOT NULL,
            record_json TEXT NOT NULL,
            CHECK (status != 'COMPLETED' OR model_version IS NOT NULL)
        );
        CREATE INDEX idx_analyses_examination ON analyses(examination_id, created_at);
        CREATE TABLE artifacts (
            analysis_id TEXT NOT NULL REFERENCES analyses(analysis_id) ON DELETE CASCADE,
            kind TEXT NOT NULL CHECK (kind IN ('MASK', 'PROBABILITY')),
            storage_key TEXT NOT NULL,
            sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
            media_type TEXT NOT NULL,
            PRIMARY KEY (analysis_id, kind)
        );
    """),
)
SCHEMA_VERSION = MIGRATIONS[-1][0]


class StorageError(Exception):
    category = "PERSISTENCE"

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message

    def to_dict(self) -> Dict[str, Any]:
        return {"category": self.category, "code": self.code, "message": self.message}


class NotFoundError(StorageError):
    pass


class BlobStore:
    """Content-addressed files: ``<root>/<sha[:2]>/<sha><suffix>``."""

    def __init__(self, root: Union[str, Path]) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, data: bytes, suffix: str = "") -> Tuple[str, str]:
        digest = hashlib.sha256(data).hexdigest()
        key = f"{digest[:2]}/{digest}{suffix}"
        path = self.root / key
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_bytes(data)
            temporary.replace(path)
        return key, digest

    def get(self, key: str) -> bytes:
        path = self.path(key)
        if not path.is_file():
            raise NotFoundError("BLOB_MISSING", f"Stored file is missing: {key}")
        return path.read_bytes()

    def path(self, key: str) -> Path:
        resolved = (self.root / key).resolve()
        if self.root.resolve() not in resolved.parents:
            raise StorageError("BLOB_KEY_INVALID", f"Invalid storage key: {key}")
        return resolved

    def delete(self, key: str) -> None:
        path = self.path(key)
        if path.exists():
            path.unlink()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


class Database:
    def __init__(self, path: Union[str, Path]) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self.migrate()

    # ------------------------------------------------------------- plumbing
    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            connection = self._connection
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except BaseException:
                connection.execute("ROLLBACK")
                raise
            else:
                connection.execute("COMMIT")

    def _query(self, sql: str, params: Sequence[Any] = ()) -> List[sqlite3.Row]:
        with self._lock:
            return self._connection.execute(sql, params).fetchall()

    def migrate(self) -> List[int]:
        applied: List[int] = []
        with self.transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, "
                       "description TEXT NOT NULL, applied_at TEXT NOT NULL)")
            done = {row[0] for row in db.execute("SELECT version FROM schema_version")}
            for version, description, sql in MIGRATIONS:
                if version in done:
                    continue
                for statement in filter(str.strip, sql.split(";")):
                    db.execute(statement)
                db.execute("INSERT INTO schema_version VALUES (?, ?, ?)", (version, description, _now()))
                applied.append(version)
        return applied

    def schema_version(self) -> int:
        return int(self._query("SELECT MAX(version) FROM schema_version")[0][0] or 0)

    def ping(self) -> bool:
        return self._query("SELECT 1")[0][0] == 1

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    @contextmanager
    def _guard(self) -> Iterator[None]:
        try:
            yield
        except sqlite3.IntegrityError as error:
            raise StorageError("INTEGRITY_VIOLATION", str(error)) from error
        except sqlite3.Error as error:
            raise StorageError("DATABASE_ERROR", str(error)) from error

    # ------------------------------------------------------------- writes
    def register_model(self, description: Dict[str, Any]) -> None:
        with self._guard(), self.transaction() as db:
            db.execute(
                "INSERT INTO model_versions VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(model_version) DO NOTHING",
                (description["model_version"], description["architecture"], description["checkpoint_sha256"],
                 description["inference_config_sha256"], json.dumps(description, sort_keys=True, default=str), _now()),
            )
            row = db.execute("SELECT checkpoint_sha256 FROM model_versions WHERE model_version = ?",
                             (description["model_version"],)).fetchone()
            if row[0] != description["checkpoint_sha256"]:
                raise StorageError("MODEL_VERSION_CONFLICT",
                                   f"model_version {description['model_version']} is already registered "
                                   "with a different checkpoint")

    def add_case(self, case: CaseRecord) -> CaseRecord:
        with self._guard(), self.transaction() as db:
            db.execute("INSERT INTO cases VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (case.case_id, case.identity_status, case.data_source, case.external_reference, case.label,
                        _iso(case.created_at), case.model_dump_json()))
        return case

    def add_examination(self, examination: ExaminationRecord) -> ExaminationRecord:
        with self._guard(), self.transaction() as db:
            self._insert_examination(db, examination)
        return examination

    @staticmethod
    def _insert_examination(db: sqlite3.Connection, examination: ExaminationRecord) -> None:
        db.execute("INSERT INTO examinations VALUES (?, ?, ?, ?, ?, ?)",
                   (examination.examination_id, examination.case_id, _iso(examination.captured_at),
                    examination.timestamp_source, _iso(examination.created_at), examination.model_dump_json()))

    def save_analysis(self, image: ImageRecord, analysis: AnalysisRecord,
                      artifacts: Sequence[Dict[str, str]] = ()) -> AnalysisRecord:
        """Insert image + analysis + artifact rows atomically."""

        if analysis.image_id != image.image_id:
            raise StorageError("INTEGRITY_VIOLATION", "analysis.image_id does not match the image record")
        if analysis.examination_id != image.examination_id:
            raise StorageError("INTEGRITY_VIOLATION", "analysis and image belong to different examinations")
        with self._guard(), self.transaction() as db:
            exists = db.execute("SELECT 1 FROM images WHERE image_id = ?", (image.image_id,)).fetchone()
            if not exists:
                db.execute("INSERT INTO images VALUES (?, ?, ?, ?, ?, ?)",
                           (image.image_id, image.examination_id, image.sha256, image.storage_key,
                            _iso(image.created_at), image.model_dump_json()))
            db.execute("INSERT INTO analyses VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (analysis.analysis_id, analysis.image_id, analysis.examination_id, analysis.status,
                        analysis.model_version, _iso(analysis.created_at), analysis.model_dump_json()))
            for artifact in artifacts:
                db.execute("INSERT INTO artifacts VALUES (?, ?, ?, ?, ?)",
                           (analysis.analysis_id, artifact["kind"], artifact["storage_key"], artifact["sha256"],
                            artifact["media_type"]))
        return analysis

    def delete_case(self, case_id: str, blobs: Optional[BlobStore] = None) -> Dict[str, int]:
        self.get_case(case_id)
        with self._guard(), self.transaction() as db:
            keys = [row[0] for row in db.execute(
                "SELECT i.storage_key FROM images i JOIN examinations e ON e.examination_id = i.examination_id "
                "WHERE e.case_id = ? AND i.storage_key IS NOT NULL UNION "
                "SELECT a.storage_key FROM artifacts a JOIN analyses n ON n.analysis_id = a.analysis_id "
                "JOIN examinations e ON e.examination_id = n.examination_id WHERE e.case_id = ?",
                (case_id, case_id))]
            counts = {
                "examinations": db.execute("SELECT COUNT(*) FROM examinations WHERE case_id = ?", (case_id,)).fetchone()[0],
                "analyses": db.execute("SELECT COUNT(*) FROM analyses n JOIN examinations e ON "
                                       "e.examination_id = n.examination_id WHERE e.case_id = ?", (case_id,)).fetchone()[0],
            }
            db.execute("DELETE FROM cases WHERE case_id = ?", (case_id,))
        removed = 0
        if blobs is not None:
            for key in keys:
                if not self._blob_referenced(key):
                    blobs.delete(key)
                    removed += 1
        return {**counts, "blobs_deleted": removed}

    def _blob_referenced(self, key: str) -> bool:
        return bool(self._query("SELECT 1 FROM images WHERE storage_key = ? UNION "
                                "SELECT 1 FROM artifacts WHERE storage_key = ? LIMIT 1", (key, key)))

    # ------------------------------------------------------------- reads
    def _one(self, sql: str, params: Sequence[Any], what: str) -> sqlite3.Row:
        rows = self._query(sql, params)
        if not rows:
            raise NotFoundError("NOT_FOUND", f"{what} not found: {params[0]}")
        return rows[0]

    def get_model(self, model_version: str) -> Dict[str, Any]:
        row = self._one("SELECT details_json FROM model_versions WHERE model_version = ?", (model_version,), "Model")
        return json.loads(row[0])

    def get_case(self, case_id: str) -> CaseRecord:
        row = self._one("SELECT record_json FROM cases WHERE case_id = ?", (case_id,), "Case")
        return CaseRecord.model_validate_json(row[0])

    def list_cases(self) -> List[CaseRecord]:
        return [CaseRecord.model_validate_json(row[0])
                for row in self._query("SELECT record_json FROM cases ORDER BY created_at, case_id")]

    def get_examination(self, examination_id: str) -> ExaminationRecord:
        row = self._one("SELECT record_json FROM examinations WHERE examination_id = ?", (examination_id,),
                        "Examination")
        return ExaminationRecord.model_validate_json(row[0])

    def list_examinations(self, case_id: str) -> List[ExaminationRecord]:
        return [ExaminationRecord.model_validate_json(row[0]) for row in self._query(
            "SELECT record_json FROM examinations WHERE case_id = ? ORDER BY captured_at, examination_id", (case_id,))]

    def get_image(self, image_id: str) -> ImageRecord:
        row = self._one("SELECT record_json FROM images WHERE image_id = ?", (image_id,), "Image")
        return ImageRecord.model_validate_json(row[0])

    def get_analysis(self, analysis_id: str) -> AnalysisRecord:
        row = self._one("SELECT record_json FROM analyses WHERE analysis_id = ?", (analysis_id,), "Analysis")
        return AnalysisRecord.model_validate_json(row[0])

    def list_analyses(self, examination_id: str) -> List[AnalysisRecord]:
        return [AnalysisRecord.model_validate_json(row[0]) for row in self._query(
            "SELECT record_json FROM analyses WHERE examination_id = ? ORDER BY created_at, analysis_id",
            (examination_id,))]

    def get_artifact(self, analysis_id: str, kind: str) -> Dict[str, str]:
        row = self._one("SELECT storage_key, sha256, media_type FROM artifacts WHERE analysis_id = ? AND kind = ?",
                        (analysis_id, kind), f"{kind} artifact")
        return {"storage_key": row[0], "sha256": row[1], "media_type": row[2]}

    def latest_analysis_per_examination(self, case_id: str) -> List[Tuple[ExaminationRecord, AnalysisRecord]]:
        """Per examination: the latest COMPLETED analysis, else the latest analysis of any status."""

        out = []
        for examination in self.list_examinations(case_id):
            completed = [a for a in self.list_analyses(examination.examination_id) if a.status == "COMPLETED"]
            if completed:
                out.append((examination, completed[-1]))
            else:
                analyses = self.list_analyses(examination.examination_id)
                if analyses:
                    out.append((examination, analyses[-1]))
        return out
