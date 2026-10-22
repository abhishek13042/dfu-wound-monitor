"""P04-S01 examination and case data contract.

Four distinct record types (REQ-P04-S01-001):

* ``CaseRecord``         - one wound under follow-up.  Identity is explicit:
                           ``identity_status`` is ``VERIFIED`` only when the
                           caller asserts a real linkage.  Public-dataset
                           samples are always ``UNVERIFIED``.
* ``ExaminationRecord``  - one visit.  ``case_id`` and ``captured_at`` may be
                           ``None`` (unknown) and are never guessed.
* ``ImageRecord``        - one image file of an examination.  The original
                           filename is stored verbatim and never parsed for
                           identifiers (REQ-P04-S01-002).
* ``AnalysisRecord``     - one pipeline run on an image (quality, model
                           output summary, measurement, provenance).

All timestamps must be timezone-aware.  Invalid input raises
``RecordValidationError`` whose ``errors`` list is machine-readable
(REQ-P04-S01-004).
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional, Type, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

SCHEMA_VERSION = "p04-s01-v1"
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
CLOCK_SKEW = timedelta(minutes=5)

IdentityStatus = Literal["VERIFIED", "UNVERIFIED", "UNKNOWN"]
TimestampSource = Literal["EXIF", "USER_ENTERED", "DEVICE", "UNKNOWN"]
AnalysisStatus = Literal["COMPLETED", "QUALITY_REJECTED", "FAILED"]


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RecordValidationError(ValueError):
    category = "VALIDATION"

    def __init__(self, record_type: str, errors: List[Dict[str, Any]]) -> None:
        self.record_type, self.errors = record_type, errors
        super().__init__(f"Invalid {record_type}: " + "; ".join(f"{e['field']}: {e['message']}" for e in errors))

    def to_dict(self) -> Dict[str, Any]:
        return {"category": self.category, "code": "RECORD_INVALID", "record_type": self.record_type,
                "errors": self.errors}


def _check_id(value: Optional[str]) -> Optional[str]:
    if value is not None and not ID_PATTERN.match(value):
        raise ValueError("must be 1-128 chars of letters, digits, '.', '_', ':' or '-'")
    return value


def _check_time(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return value
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def create(cls: Type["R"], **data: Any) -> "R":
        """Validate and build; raises ``RecordValidationError`` on failure."""

        try:
            return cls.model_validate(data)
        except ValidationError as error:
            raise RecordValidationError(cls.__name__, [
                {"field": ".".join(str(p) for p in item["loc"]) or "__root__", "code": item["type"],
                 "message": item["msg"]}
                for item in error.errors()
            ]) from None

    @classmethod
    def from_json(cls: Type["R"], text: str) -> "R":
        try:
            return cls.model_validate_json(text)
        except ValidationError as error:
            raise RecordValidationError(cls.__name__, [
                {"field": ".".join(str(p) for p in item["loc"]) or "__root__", "code": item["type"],
                 "message": item["msg"]}
                for item in error.errors()
            ]) from None

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


R = TypeVar("R", bound=_Record)


class CaseRecord(_Record):
    case_id: str = Field(default_factory=lambda: new_id("case"))
    identity_status: IdentityStatus = "UNKNOWN"
    external_reference: Optional[str] = None   # opaque, caller-supplied; never derived
    data_source: str = "USER_UPLOAD"           # e.g. USER_UPLOAD, FUSEG2021, SYNTHETIC
    label: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)

    check_ids = field_validator("case_id")(_check_id)
    check_times = field_validator("created_at")(_check_time)

    @model_validator(mode="after")
    def _public_data_is_not_a_verified_patient(self) -> "CaseRecord":
        if self.data_source.upper() not in ("USER_UPLOAD", "SYNTHETIC") and self.identity_status == "VERIFIED":
            raise ValueError(f"{self.data_source} samples have no verified patient linkage")
        return self


class ExaminationRecord(_Record):
    examination_id: str = Field(default_factory=lambda: new_id("exam"))
    case_id: Optional[str] = None              # None = unknown, never inferred
    captured_at: Optional[datetime] = None     # None = unknown
    timestamp_source: TimestampSource = "UNKNOWN"
    notes: Optional[str] = Field(default=None, max_length=2000)
    created_at: datetime = Field(default_factory=utc_now)

    check_ids = field_validator("examination_id", "case_id")(_check_id)
    check_times = field_validator("captured_at", "created_at")(_check_time)

    @model_validator(mode="after")
    def _consistent_time(self) -> "ExaminationRecord":
        if self.captured_at is None and self.timestamp_source != "UNKNOWN":
            raise ValueError("timestamp_source must be UNKNOWN when captured_at is missing")
        if self.captured_at is not None:
            if self.timestamp_source == "UNKNOWN":
                raise ValueError("captured_at needs a timestamp_source")
            if self.captured_at > utc_now() + CLOCK_SKEW:
                raise ValueError("captured_at is in the future")
        return self


class ImageRecord(_Record):
    image_id: str = Field(default_factory=lambda: new_id("img"))
    examination_id: Optional[str] = None
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    original_filename: Optional[str] = Field(default=None, max_length=512)  # stored verbatim, never parsed
    format: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    storage_key: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)

    check_ids = field_validator("image_id", "examination_id")(_check_id)
    check_times = field_validator("created_at")(_check_time)


class AnalysisRecord(_Record):
    analysis_id: str = Field(default_factory=lambda: new_id("ana"))
    image_id: str
    examination_id: Optional[str] = None
    status: AnalysisStatus
    quality: Dict[str, Any]
    model_version: Optional[str] = None
    inference_summary: Optional[Dict[str, Any]] = None
    measurement: Optional[Dict[str, Any]] = None
    calibration: Optional[Dict[str, Any]] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=utc_now)

    check_ids = field_validator("analysis_id", "image_id", "examination_id")(_check_id)
    check_times = field_validator("created_at")(_check_time)

    @model_validator(mode="after")
    def _status_consistency(self) -> "AnalysisRecord":
        if self.status == "COMPLETED":
            if self.measurement is None or self.model_version is None:
                raise ValueError("COMPLETED analyses need a measurement and model_version")
            for section in ("input", "model", "preprocessing", "postprocessing"):
                if section not in self.provenance:
                    raise ValueError(f"provenance.{section} is required for COMPLETED analyses")
        elif self.status == "QUALITY_REJECTED":
            if self.measurement is not None:
                raise ValueError("QUALITY_REJECTED analyses must not carry a measurement")
            if self.quality.get("status") != "REJECTED":
                raise ValueError("QUALITY_REJECTED analyses need a REJECTED quality result")
        elif self.error is None:
            raise ValueError("FAILED analyses need an error")
        return self

    @property
    def measurement_basis(self) -> Optional[str]:
        return (self.measurement or {}).get("measurement_basis")


def image_record_from_outcome(outcome: Any, examination_id: Optional[str], original_filename: Optional[str] = None,
                              storage_key: Optional[str] = None, image_id: Optional[str] = None) -> ImageRecord:
    decoded = outcome.decoded
    return ImageRecord.create(image_id=image_id or new_id("img"), examination_id=examination_id,
                              sha256=decoded.sha256, original_filename=original_filename,
                              format=decoded.source_format, width=decoded.width, height=decoded.height,
                              storage_key=storage_key)


def analysis_record_from_outcome(outcome: Any, image: ImageRecord, analysis_id: Optional[str] = None) -> AnalysisRecord:
    """Map an ``AnalysisOutcome`` (src.inference.pipeline) to a record."""

    data: Dict[str, Any] = {
        "analysis_id": analysis_id or new_id("ana"),
        "image_id": image.image_id,
        "examination_id": image.examination_id,
        "status": outcome.status,
        "quality": outcome.quality.to_dict(),
        "warnings": outcome.warnings,
        "provenance": {"request_id": outcome.request_id,
                       "input": {"sha256": image.sha256, "format": image.format,
                                 "width": image.width, "height": image.height}},
    }
    if outcome.inference is not None:
        summary = outcome.inference.summary()
        provenance = summary.pop("provenance")
        data["provenance"] = provenance
        data["inference_summary"] = summary
        data["model_version"] = provenance["model"]["model_version"]
    if outcome.measurement is not None:
        measurement = outcome.measurement.to_dict()
        data["provenance"] = {**data["provenance"], "measurement": measurement["provenance"].get("measurement")}
        measurement.pop("provenance")
        data["measurement"] = measurement
        data["calibration"] = measurement.get("calibration")
    return AnalysisRecord.create(**data)
