"""P07-S02 repository: all database access goes through this class.

* Separate tables and identifiers for model versions, cases, examinations,
  images, analyses and artifacts (REQ-P05-S02-001).
* Each analysis row keeps the full validated record (provenance included) and
  references the stored input image and the mask artifacts by SHA-256
  (REQ-P05-S02-002).
* Records are validated by the P04 schemas before anything is written.  Each
  public method is one transaction, and foreign keys and CHECK constraints are
  enforced, so a bad write leaves nothing behind (REQ-P05-S02-003).
* An instance acts for one owner, and every read and write of user data is
  filtered by it, so a route cannot forget the check (REQ-P07-S04-002).  Only
  ``register_model``, ``get_model``, ``blob_referenced``, ``expire_uploads``,
  ``ensure_user`` and the worker's job methods are global.  v1 stays on the
  default ``demo`` owner.
"""

from __future__ import annotations

import copy
import json
import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from sqlalchemy import CursorResult, delete, func, select, text, union, update
from sqlalchemy.exc import DataError, IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from src.longitudinal.records import AnalysisRecord, CaseRecord, ExaminationRecord, ImageRecord, new_id
from src.storage import models
from src.storage.blobs import BlobStore, staging_key
from src.storage.database import (
    NotFoundError,
    StorageError,
    create_database_engine,
    database_url,
    installed_version,
    is_sqlite,
    migrate,
)
from src.worker.state import QUEUED, RUNNING, require_transition

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _changed(session: Session, statement: Any) -> bool:
    return cast("CursorResult[Any]", session.execute(statement)).rowcount == 1


def _job(row: models.AnalysisJob) -> dict[str, Any]:
    return {"analysis_id": row.analysis_id, "owner_id": row.owner_id, "upload_id": row.upload_id,
            "examination_id": row.examination_id, "status": row.status, "attempts": row.attempts,
            "requeued": row.requeued, "request": json.loads(row.request_json),
            "error": json.loads(row.error_json) if row.error_json else None}


class Repository:
    def __init__(self, target: str | Path, owner_id: str = models.DEMO_OWNER) -> None:
        self.url = database_url(target)
        self.owner_id = owner_id
        self.path: str | None = None
        if is_sqlite(self.url):
            self.path = self.url.removeprefix("sqlite:///")
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_database_engine(self.url)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)
        self._closed = False
        if self.path is not None:
            self.migrate()

    def for_owner(self, owner_id: str) -> Repository:
        """The same connection pool, scoped to one user."""

        scoped = copy.copy(self)
        scoped.owner_id = owner_id
        return scoped

    # ------------------------------------------------------------- plumbing
    @contextmanager
    def _session(self) -> Iterator[Session]:
        if self._closed:
            raise StorageError("DATABASE_ERROR", "The database connection is closed")
        try:
            with self._sessions.begin() as session:
                yield session
        except (IntegrityError, DataError) as error:
            detail = str(error.orig).splitlines() or ["Constraint violated"]
            raise StorageError("INTEGRITY_VIOLATION", detail[0]) from error
        except SQLAlchemyError as error:
            # The driver's text can name the host, so it goes to the log only.
            log.exception("Database operation failed")
            raise StorageError("DATABASE_ERROR", "The database operation failed") from error

    def migrate(self) -> list[int]:
        try:
            return migrate(self.url)
        except SQLAlchemyError as error:
            log.exception("Migration failed")
            raise StorageError("DATABASE_ERROR", "The database migration failed") from error

    def schema_version(self) -> int:
        with self._session() as session:
            return installed_version(session.connection())

    def ping(self) -> bool:
        with self._session() as session:
            return session.execute(text("SELECT 1")).scalar_one() == 1

    def close(self) -> None:
        self._closed = True
        self.engine.dispose()

    def _require_owned(self, session: Session, model: Any, column: Any, key: str) -> bool:
        """Whether the row exists.  Another owner's row looks like a missing one."""

        owner = session.scalar(select(model.owner_id).where(column == key))
        if owner is not None and owner != self.owner_id:
            raise NotFoundError("NOT_FOUND", f"{model.__name__} not found: {key}")
        return owner is not None

    # ------------------------------------------------------------- accounts
    def ensure_user(self, subject: str) -> str:
        """The user ID for a verified token subject, created on first sign-in."""

        lookup = select(models.User.user_id).where(models.User.subject == subject)
        with self._session() as session:
            user_id = session.scalar(lookup)
        if user_id is not None:
            return user_id
        user_id = new_id("usr")
        try:
            with self._session() as session:
                session.add(models.User(user_id=user_id, subject=subject, created_at=_now()))
            return user_id
        except StorageError:
            # A concurrent first request may have created it.
            with self._session() as session:
                existing = session.scalar(lookup)
            if existing is None:
                raise
            return existing

    def delete_account(self, blobs: BlobStore) -> dict[str, int]:
        """Blobs go first, so a failure leaves the rows that let the delete be retried."""

        if self.owner_id == models.DEMO_OWNER:
            raise StorageError("DEMO_ACCOUNT", "The demo workspace is not an account")
        with self._session() as session:
            counts = {name: session.scalar(select(func.count()).select_from(model)
                                           .where(model.owner_id == self.owner_id)) or 0
                      for name, model in (("cases", models.Case), ("examinations", models.Examination),
                                          ("images", models.Image), ("analyses", models.Analysis),
                                          ("uploads", models.Upload))}
            keys: set[str | None] = set(session.scalars(union(
                select(models.Image.storage_key).where(models.Image.owner_id == self.owner_id),
                select(models.Artifact.storage_key).join(
                    models.Analysis, models.Analysis.analysis_id == models.Artifact.analysis_id,
                ).where(models.Analysis.owner_id == self.owner_id),
                select(models.Upload.storage_key).where(models.Upload.owner_id == self.owner_id),
            )).all())
            upload_ids = session.scalars(select(models.Upload.upload_id)
                                         .where(models.Upload.owner_id == self.owner_id)).all()
        for upload_id in upload_ids:
            blobs.delete(staging_key(upload_id))
        removed = 0
        for key in filter(None, keys):
            if not self.blob_referenced(key, except_owner=self.owner_id):  # identical bytes may be someone else's
                blobs.delete(key)
                removed += 1
        with self._session() as session:
            session.execute(delete(models.User).where(models.User.user_id == self.owner_id))
        return {**counts, "blobs_deleted": removed}

    def export(self) -> dict[str, list[dict[str, Any]]]:
        def records(model: Any) -> list[dict[str, Any]]:
            rows = session.scalars(select(model.record_json).where(model.owner_id == self.owner_id)
                                   .order_by(model.created_at)).all()
            return [json.loads(row) for row in rows]

        with self._session() as session:
            data = {"cases": records(models.Case), "examinations": records(models.Examination),
                    "images": records(models.Image), "analyses": records(models.Analysis)}
            rows = session.execute(
                select(models.Artifact.analysis_id, models.Artifact.kind, models.Artifact.storage_key,
                       models.Artifact.sha256, models.Artifact.media_type)
                .join(models.Analysis, models.Analysis.analysis_id == models.Artifact.analysis_id)
                .where(models.Analysis.owner_id == self.owner_id)).all()
        data["artifacts"] = [dict(row._mapping) for row in rows]
        return data

    # ------------------------------------------------------------- writes
    def _registered_checkpoint(self, model_version: str) -> str | None:
        with self._session() as session:
            return session.scalar(select(models.ModelVersion.checkpoint_sha256)
                                  .where(models.ModelVersion.model_version == model_version))

    def register_model(self, description: dict[str, Any]) -> None:
        model_version = description["model_version"]
        if self._registered_checkpoint(model_version) is None:
            try:
                with self._session() as session:
                    session.add(models.ModelVersion(
                        model_version=model_version, architecture=description["architecture"],
                        checkpoint_sha256=description["checkpoint_sha256"],
                        inference_config_sha256=description["inference_config_sha256"],
                        details_json=json.dumps(description, sort_keys=True, default=str), registered_at=_now()))
            except StorageError:
                # Another instance may have registered it first.
                if self._registered_checkpoint(model_version) is None:
                    raise
        if self._registered_checkpoint(model_version) != description["checkpoint_sha256"]:
            raise StorageError("MODEL_VERSION_CONFLICT",
                               f"model_version {model_version} is already registered with a different checkpoint")

    def add_case(self, case: CaseRecord) -> CaseRecord:
        with self._session() as session:
            session.add(models.Case(
                case_id=case.case_id, owner_id=self.owner_id, identity_status=case.identity_status, data_source=case.data_source,
                external_reference=case.external_reference, label=case.label, created_at=_iso(case.created_at),
                record_json=case.model_dump_json()))
        return case

    def add_examination(self, examination: ExaminationRecord) -> ExaminationRecord:
        with self._session() as session:
            if examination.case_id is not None:
                self._require_owned(session, models.Case, models.Case.case_id, examination.case_id)
            session.add(models.Examination(
                examination_id=examination.examination_id, owner_id=self.owner_id, case_id=examination.case_id,
                captured_at=_iso(examination.captured_at), timestamp_source=examination.timestamp_source,
                created_at=_iso(examination.created_at), record_json=examination.model_dump_json()))
        return examination

    def save_analysis(self, image: ImageRecord, analysis: AnalysisRecord,
                      artifacts: Sequence[dict[str, str]] = ()) -> AnalysisRecord:
        """Insert image + analysis + artifact rows atomically."""

        if analysis.image_id != image.image_id:
            raise StorageError("INTEGRITY_VIOLATION", "analysis.image_id does not match the image record")
        if analysis.examination_id != image.examination_id:
            raise StorageError("INTEGRITY_VIOLATION", "analysis and image belong to different examinations")
        with self._session() as session:
            if image.examination_id is not None:
                self._require_owned(session, models.Examination, models.Examination.examination_id,
                                    image.examination_id)
            if not self._require_owned(session, models.Image, models.Image.image_id, image.image_id):
                session.add(models.Image(
                    image_id=image.image_id, owner_id=self.owner_id, examination_id=image.examination_id,
                    sha256=image.sha256,
                    storage_key=image.storage_key, created_at=_iso(image.created_at),
                    record_json=image.model_dump_json()))
                session.flush()  # the tables have no ORM relationships to order the inserts
            session.add(models.Analysis(
                analysis_id=analysis.analysis_id, owner_id=self.owner_id, image_id=analysis.image_id,
                examination_id=analysis.examination_id, status=analysis.status, model_version=analysis.model_version, created_at=_iso(analysis.created_at),
                record_json=analysis.model_dump_json()))
            session.flush()
            session.add_all(models.Artifact(
                analysis_id=analysis.analysis_id, kind=artifact["kind"], storage_key=artifact["storage_key"],
                sha256=artifact["sha256"], media_type=artifact["media_type"]) for artifact in artifacts)
        return analysis

    def delete_case(self, case_id: str, blobs: BlobStore | None = None) -> dict[str, int]:
        self.get_case(case_id)
        examination_ids = select(models.Examination.examination_id).where(models.Examination.case_id == case_id)
        with self._session() as session:
            keys: Sequence[str | None] = session.scalars(union(
                select(models.Image.storage_key).where(models.Image.examination_id.in_(examination_ids),
                                                       models.Image.storage_key.is_not(None)),
                select(models.Artifact.storage_key).join(
                    models.Analysis, models.Analysis.analysis_id == models.Artifact.analysis_id,
                ).where(models.Analysis.examination_id.in_(examination_ids)),
            )).all()
            counts = {
                "examinations": session.scalar(select(func.count()).select_from(models.Examination)
                                               .where(models.Examination.case_id == case_id)) or 0,
                "analyses": session.scalar(select(func.count()).select_from(models.Analysis)
                                           .where(models.Analysis.examination_id.in_(examination_ids))) or 0,
            }
            session.execute(delete(models.Case).where(models.Case.case_id == case_id,
                                                      models.Case.owner_id == self.owner_id))
        removed = 0
        if blobs is not None:
            for key in keys:
                if key is not None and not self.blob_referenced(key):
                    blobs.delete(key)
                    removed += 1
        return {**counts, "blobs_deleted": removed}

    def blob_referenced(self, key: str, except_owner: str | None = None) -> bool:
        images = select(models.Image.storage_key).where(models.Image.storage_key == key)
        artifacts = select(models.Artifact.storage_key).join(
            models.Analysis, models.Analysis.analysis_id == models.Artifact.analysis_id,
        ).where(models.Artifact.storage_key == key)
        uploads = select(models.Upload.storage_key).where(models.Upload.storage_key == key)
        if except_owner is not None:
            images = images.where(models.Image.owner_id != except_owner)
            artifacts = artifacts.where(models.Analysis.owner_id != except_owner)
            uploads = uploads.where(models.Upload.owner_id != except_owner)
        with self._session() as session:
            return session.scalars(union(images, artifacts, uploads).limit(1)).first() is not None

    # ------------------------------------------------------------- uploads
    def add_upload(self, upload_id: str, *, filename: str, declared_size: int, declared_sha256: str,
                   expires_at: str) -> None:
        with self._session() as session:
            session.add(models.Upload(upload_id=upload_id, owner_id=self.owner_id, status="PENDING", filename=filename,
                                      declared_size=declared_size, declared_sha256=declared_sha256,
                                      created_at=_now(), expires_at=expires_at))

    def get_upload(self, upload_id: str) -> dict[str, Any]:
        with self._session() as session:
            row = session.get(models.Upload, upload_id)
            if row is None or row.owner_id != self.owner_id:
                raise NotFoundError("NOT_FOUND", f"Upload not found: {upload_id}")
            return {column.name: getattr(row, column.name) for column in models.Upload.__table__.columns}

    def finish_upload(self, upload_id: str, status: str, **fields: Any) -> dict[str, Any]:
        """Leave PENDING exactly once; a concurrent verify sees the finished row."""

        with self._session() as session:
            session.execute(update(models.Upload)
                            .where(models.Upload.upload_id == upload_id, models.Upload.status == "PENDING",
                                   models.Upload.owner_id == self.owner_id)
                            .values(status=status, **fields))
        return self.get_upload(upload_id)

    def delete_upload(self, upload_id: str) -> None:
        with self._session() as session:
            session.execute(delete(models.Upload).where(models.Upload.upload_id == upload_id,
                                                        models.Upload.owner_id == self.owner_id))

    def expire_uploads(self, blobs: BlobStore, limit: int = 20) -> int:
        """Remove expired rows and the objects only they kept alive."""

        with self._session() as session:
            rows = session.execute(select(models.Upload.upload_id, models.Upload.storage_key)
                                   .where(models.Upload.expires_at <= _now())
                                   .order_by(models.Upload.expires_at).limit(limit)).all()
            session.execute(delete(models.Upload).where(models.Upload.upload_id.in_([row[0] for row in rows])))
        for upload_id, storage_key in rows:
            blobs.delete(staging_key(upload_id))
            if storage_key is not None and not self.blob_referenced(storage_key):
                blobs.delete(storage_key)
        return len(rows)

    def extend_upload(self, upload_id: str, expires_at: str) -> None:
        with self._session() as session:
            session.execute(update(models.Upload).where(models.Upload.upload_id == upload_id,
                                                        models.Upload.owner_id == self.owner_id)
                            .values(expires_at=expires_at))

    # ------------------------------------------------------------- analysis jobs
    def add_job(self, analysis_id: str, upload_id: str, examination_id: str | None,
                request: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        job = models.AnalysisJob(analysis_id=analysis_id, owner_id=self.owner_id, upload_id=upload_id,
                                 examination_id=examination_id, status=QUEUED, attempts=0, requeued=0,
                                 request_json=json.dumps(request, sort_keys=True), created_at=now, updated_at=now)
        with self._session() as session:
            session.add(job)
        return _job(job)

    def job_for_upload(self, upload_id: str) -> dict[str, Any] | None:
        with self._session() as session:
            row = session.scalar(select(models.AnalysisJob).where(models.AnalysisJob.upload_id == upload_id,
                                                                  models.AnalysisJob.owner_id == self.owner_id))
            return _job(row) if row is not None else None

    def find_job(self, analysis_id: str) -> dict[str, Any] | None:
        with self._session() as session:
            row = session.get(models.AnalysisJob, analysis_id)
            return _job(row) if row is not None and row.owner_id == self.owner_id else None

    def delete_job(self, analysis_id: str) -> None:
        """Withdraw a job no worker has touched.  One that has started is left alone."""

        with self._session() as session:
            session.execute(delete(models.AnalysisJob).where(
                models.AnalysisJob.analysis_id == analysis_id, models.AnalysisJob.owner_id == self.owner_id,
                models.AnalysisJob.status == QUEUED, models.AnalysisJob.attempts == 0))

    def has_analysis(self, analysis_id: str) -> bool:
        with self._session() as session:
            return session.scalar(select(models.Analysis.status).where(
                models.Analysis.analysis_id == analysis_id, models.Analysis.owner_id == self.owner_id)) is not None

    def load_job(self, analysis_id: str) -> dict[str, Any]:
        with self._session() as session:
            row = session.get(models.AnalysisJob, analysis_id)
            if row is None:
                raise NotFoundError("NOT_FOUND", f"Job not found: {analysis_id}")
            return _job(row)

    def claim_job(self, analysis_id: str) -> dict[str, Any] | None:
        """Only one caller can win, so a redelivered message finds nothing to do."""

        with self._session() as session:
            won = _changed(session, update(models.AnalysisJob)
                           .where(models.AnalysisJob.analysis_id == analysis_id, models.AnalysisJob.status == QUEUED)
                           .values(status=RUNNING, attempts=models.AnalysisJob.attempts + 1, updated_at=_now()))
            if not won:
                return None
            return _job(session.get_one(models.AnalysisJob, analysis_id))

    def move_job(self, analysis_id: str, current: str, target: str, *, error: dict[str, Any] | None = None,
                 requeued: int | None = None) -> bool:
        """False when the job is no longer in ``current``, for example because its owner was deleted."""

        require_transition(current, target)
        values: dict[str, Any] = {"status": target, "updated_at": _now()}
        if error is not None:
            values["error_json"] = json.dumps(error, sort_keys=True)
        if requeued is not None:
            values["requeued"] = requeued
        with self._session() as session:
            return _changed(session, update(models.AnalysisJob).where(
                models.AnalysisJob.analysis_id == analysis_id, models.AnalysisJob.status == current).values(**values))

    def overdue_jobs(self, status: str, before: str) -> list[dict[str, Any]]:
        with self._session() as session:
            rows = session.scalars(select(models.AnalysisJob).where(models.AnalysisJob.status == status,
                                                                    models.AnalysisJob.updated_at <= before)).all()
            return [_job(row) for row in rows]

    def analysis_status(self, analysis_id: str) -> str | None:
        with self._session() as session:
            return session.scalar(select(models.Analysis.status).where(models.Analysis.analysis_id == analysis_id))

    # ------------------------------------------------------------- reads
    def _one(self, statement: Any, key: str, what: str) -> Any:
        with self._session() as session:
            value = session.execute(statement).first()
        if value is None:
            raise NotFoundError("NOT_FOUND", f"{what} not found: {key}")
        return value

    def get_model(self, model_version: str) -> dict[str, Any]:
        row = self._one(select(models.ModelVersion.details_json)
                        .where(models.ModelVersion.model_version == model_version), model_version, "Model")
        return json.loads(row[0])

    def get_case(self, case_id: str) -> CaseRecord:
        row = self._one(select(models.Case.record_json).where(models.Case.case_id == case_id,
                                                              models.Case.owner_id == self.owner_id),
                        case_id, "Case")
        return CaseRecord.model_validate_json(row[0])

    def list_cases(self) -> list[CaseRecord]:
        with self._session() as session:
            rows = session.scalars(select(models.Case.record_json).where(models.Case.owner_id == self.owner_id)
                                   .order_by(models.Case.created_at, models.Case.case_id)).all()
        return [CaseRecord.model_validate_json(row) for row in rows]

    def get_examination(self, examination_id: str) -> ExaminationRecord:
        row = self._one(select(models.Examination.record_json)
                        .where(models.Examination.examination_id == examination_id,
                               models.Examination.owner_id == self.owner_id), examination_id, "Examination")
        return ExaminationRecord.model_validate_json(row[0])

    def list_examinations(self, case_id: str) -> list[ExaminationRecord]:
        # NULLS FIRST is explicit because the two databases default to opposite ends.
        with self._session() as session:
            rows = session.scalars(select(models.Examination.record_json)
                                   .where(models.Examination.case_id == case_id,
                                          models.Examination.owner_id == self.owner_id)
                                   .order_by(models.Examination.captured_at.asc().nulls_first(),
                                             models.Examination.examination_id)).all()
        return [ExaminationRecord.model_validate_json(row) for row in rows]

    def get_image(self, image_id: str) -> ImageRecord:
        row = self._one(select(models.Image.record_json).where(models.Image.image_id == image_id,
                                                               models.Image.owner_id == self.owner_id),
                        image_id, "Image")
        return ImageRecord.model_validate_json(row[0])

    def get_analysis(self, analysis_id: str) -> AnalysisRecord:
        row = self._one(select(models.Analysis.record_json).where(models.Analysis.analysis_id == analysis_id,
                                                                  models.Analysis.owner_id == self.owner_id),
                        analysis_id, "Analysis")
        return AnalysisRecord.model_validate_json(row[0])

    def list_analyses(self, examination_id: str) -> list[AnalysisRecord]:
        with self._session() as session:
            rows = session.scalars(select(models.Analysis.record_json)
                                   .where(models.Analysis.examination_id == examination_id,
                                          models.Analysis.owner_id == self.owner_id)
                                   .order_by(models.Analysis.created_at, models.Analysis.analysis_id)).all()
        return [AnalysisRecord.model_validate_json(row) for row in rows]

    def get_artifact(self, analysis_id: str, kind: str) -> dict[str, str]:
        row = self._one(select(models.Artifact.storage_key, models.Artifact.sha256, models.Artifact.media_type)
                        .join(models.Analysis, models.Analysis.analysis_id == models.Artifact.analysis_id)
                        .where(models.Artifact.analysis_id == analysis_id, models.Artifact.kind == kind,
                               models.Analysis.owner_id == self.owner_id),
                        analysis_id, f"{kind} artifact")
        return {"storage_key": row[0], "sha256": row[1], "media_type": row[2]}

    def latest_analysis_per_examination(self, case_id: str) -> list[tuple[ExaminationRecord, AnalysisRecord]]:
        """Per examination: the latest COMPLETED analysis, else the latest analysis of any status."""

        out = []
        for examination in self.list_examinations(case_id):
            analyses = self.list_analyses(examination.examination_id)
            completed = [analysis for analysis in analyses if analysis.status == "COMPLETED"]
            if completed:
                out.append((examination, completed[-1]))
            elif analyses:
                out.append((examination, analyses[-1]))
        return out
