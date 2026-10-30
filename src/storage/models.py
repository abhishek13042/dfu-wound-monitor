"""P07-S02 typed table definitions.

Table names and columns match the P05-S02 schema.  ``*_json`` columns keep the
full validated record as text and timestamps stay ISO 8601 text, so a record
reads back identically on SQLite and PostgreSQL.  Every constraint is named,
because Alembic needs a name to alter one later.

P07-S04: every row a user can reach carries ``owner_id``.  ``artifacts`` belong
to their analysis.  The ``demo`` user has no subject, so no token can reach it.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, MetaData, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ix": "ix_%(table_name)s_%(column_0_name)s",
}
DEMO_OWNER = "demo"


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    subject: Mapped[str | None] = mapped_column(Text, unique=True)
    created_at: Mapped[str] = mapped_column(Text)


def _owner_column() -> Mapped[str]:
    return mapped_column(Text, ForeignKey("users.user_id", ondelete="CASCADE"))


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (
        CheckConstraint("length(checkpoint_sha256) = 64", name="checkpoint_sha256_length"),
        CheckConstraint("length(inference_config_sha256) = 64", name="inference_config_sha256_length"),
    )

    model_version: Mapped[str] = mapped_column(Text, primary_key=True)
    architecture: Mapped[str] = mapped_column(Text)
    checkpoint_sha256: Mapped[str] = mapped_column(Text)
    inference_config_sha256: Mapped[str] = mapped_column(Text)
    details_json: Mapped[str] = mapped_column(Text)
    registered_at: Mapped[str] = mapped_column(Text)


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (
        CheckConstraint("identity_status IN ('VERIFIED', 'UNVERIFIED', 'UNKNOWN')", name="identity_status"),
        Index("idx_cases_owner", "owner_id"),
    )

    case_id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = _owner_column()
    identity_status: Mapped[str] = mapped_column(Text)
    data_source: Mapped[str] = mapped_column(Text)
    external_reference: Mapped[str | None] = mapped_column(Text)
    label: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)
    record_json: Mapped[str] = mapped_column(Text)


class Examination(Base):
    __tablename__ = "examinations"
    __table_args__ = (
        Index("idx_examinations_case", "case_id", "captured_at"),
        Index("idx_examinations_owner", "owner_id"),
    )

    examination_id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = _owner_column()
    case_id: Mapped[str | None] = mapped_column(Text, ForeignKey("cases.case_id", ondelete="CASCADE"))
    captured_at: Mapped[str | None] = mapped_column(Text)
    timestamp_source: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)
    record_json: Mapped[str] = mapped_column(Text)


class Image(Base):
    __tablename__ = "images"
    __table_args__ = (
        CheckConstraint("length(sha256) = 64", name="sha256_length"),
        Index("idx_images_examination", "examination_id"),
        Index("idx_images_owner", "owner_id"),
    )

    image_id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = _owner_column()
    examination_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("examinations.examination_id", ondelete="CASCADE"))
    sha256: Mapped[str] = mapped_column(Text)
    storage_key: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)
    record_json: Mapped[str] = mapped_column(Text)


class Analysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (
        CheckConstraint("status IN ('COMPLETED', 'QUALITY_REJECTED', 'FAILED')", name="status"),
        CheckConstraint("status != 'COMPLETED' OR model_version IS NOT NULL", name="completed_has_model"),
        Index("idx_analyses_examination", "examination_id", "created_at"),
        Index("idx_analyses_owner", "owner_id"),
    )

    analysis_id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = _owner_column()
    image_id: Mapped[str] = mapped_column(Text, ForeignKey("images.image_id", ondelete="CASCADE"))
    examination_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("examinations.examination_id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(Text)
    model_version: Mapped[str | None] = mapped_column(Text, ForeignKey("model_versions.model_version"))
    created_at: Mapped[str] = mapped_column(Text)
    record_json: Mapped[str] = mapped_column(Text)


class Upload(Base):
    __tablename__ = "uploads"
    __table_args__ = (
        CheckConstraint("status IN ('PENDING', 'VERIFIED', 'REJECTED')", name="status"),
        CheckConstraint("length(declared_sha256) = 64", name="declared_sha256_length"),
        Index("idx_uploads_expires", "expires_at"),
        Index("idx_uploads_owner", "owner_id"),
    )

    upload_id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = _owner_column()
    status: Mapped[str] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(Text)
    declared_size: Mapped[int] = mapped_column(Integer)
    declared_sha256: Mapped[str] = mapped_column(Text)
    storage_key: Mapped[str | None] = mapped_column(Text)
    format: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[str] = mapped_column(Text)


class AnalysisJob(Base):
    """P07-S05: a job is a request in progress, and an ``analyses`` row is a finished result."""

    __tablename__ = "analysis_jobs"
    __table_args__ = (
        CheckConstraint("status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'QUALITY_REJECTED', 'FAILED')",
                        name="job_status"),
        Index("idx_analysis_jobs_status", "status", "updated_at"),
        Index("idx_analysis_jobs_owner", "owner_id"),
    )

    analysis_id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = _owner_column()
    upload_id: Mapped[str] = mapped_column(Text, unique=True)
    examination_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("examinations.examination_id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer)
    requeued: Mapped[int] = mapped_column(Integer)
    request_json: Mapped[str] = mapped_column(Text)
    error_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text)


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        CheckConstraint("kind IN ('MASK', 'PROBABILITY')", name="kind"),
        CheckConstraint("length(sha256) = 64", name="sha256_length"),
    )

    analysis_id: Mapped[str] = mapped_column(
        Text, ForeignKey("analyses.analysis_id", ondelete="CASCADE"), primary_key=True)
    kind: Mapped[str] = mapped_column(Text, primary_key=True)
    storage_key: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(Text)
