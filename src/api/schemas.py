"""Versioned API schemas (REQ-P05-S01-001).

Every response carries ``api_version``.  The schema names are part of the
contract: a breaking change bumps ``API_VERSION`` and the URL prefix.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

API_VERSION = "v1"
API_V2 = "v2"
ErrorCategory = Literal["INVALID_INPUT", "QUALITY_REJECTED", "MODEL_FAILURE", "MODEL_NOT_READY",
                        "INFRASTRUCTURE_FAILURE", "NOT_FOUND", "CONFLICT", "UNAUTHENTICATED", "BUSY"]
# REQ-P06-S02-003: every failure belongs to exactly one operational class.
FailureClass = Literal["INPUT", "QUALITY", "MODEL", "PERSISTENCE", "SERVICE"]


class _Response(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_version: str = API_VERSION


class ErrorBody(BaseModel):
    category: ErrorCategory
    failure_class: FailureClass
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(_Response):
    error: ErrorBody
    request_id: str | None = None
    analysis: AnalysisResponse | None = None


class LiveResponse(_Response):
    status: Literal["ALIVE"] = "ALIVE"
    service_version: str


class ReadinessResponse(_Response):
    status: Literal["READY", "NOT_READY"]
    service: Literal["READY"] = "READY"
    model: Literal["READY", "NOT_READY"]
    database: Literal["READY", "NOT_READY"]
    storage: Literal["READY", "NOT_READY"]
    queue: Literal["READY", "NOT_READY"]
    model_version: str | None = None
    schema_version: int | None = None
    detail: dict[str, Any] | None = None


class ModelInfoResponse(_Response):
    model: dict[str, Any]
    quality_config: dict[str, Any]
    measurement_config: dict[str, Any]
    limitations: list[str]


class CaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identity_status: Literal["VERIFIED", "UNVERIFIED", "UNKNOWN"] = "UNKNOWN"
    external_reference: str | None = Field(default=None, max_length=200)
    label: str | None = Field(default=None, max_length=200)
    data_source: str = Field(default="USER_UPLOAD", max_length=64)


class ExaminationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    captured_at: datetime | None = None
    timestamp_source: Literal["EXIF", "USER_ENTERED", "DEVICE", "UNKNOWN"] = "UNKNOWN"
    notes: str | None = Field(default=None, max_length=2000)


class CaseResponse(_Response):
    case: dict[str, Any]
    examinations: list[dict[str, Any]] | None = None


class CaseListResponse(_Response):
    cases: list[dict[str, Any]]


class ExaminationResponse(_Response):
    examination: dict[str, Any]
    analyses: list[dict[str, Any]] | None = None


class AnalysisResponse(_Response):
    schema_name: Literal["AnalysisResponse"] = "AnalysisResponse"
    analysis_id: str
    status: Literal["COMPLETED", "QUALITY_REJECTED", "FAILED"]
    image: dict[str, Any]
    quality: dict[str, Any]
    model_version: str | None
    measurement: dict[str, Any] | None
    inference: dict[str, Any] | None
    warnings: list[dict[str, Any]]
    provenance: dict[str, Any]
    links: dict[str, str]
    limitation: str


class TrendResponse(_Response):
    trend: dict[str, Any]


class ComparisonResponse(_Response):
    comparison: dict[str, Any]


class DeleteResponse(_Response):
    deleted: dict[str, Any]


class ExportResponse(_Response):
    cases: list[dict[str, Any]]
    examinations: list[dict[str, Any]]
    images: list[dict[str, Any]]
    analyses: list[dict[str, Any]]
    artifacts: list[dict[str, Any]]
    url_expires_in_seconds: int


ErrorResponse.model_rebuild()
