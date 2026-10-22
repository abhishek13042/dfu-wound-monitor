"""Versioned API schemas (REQ-P05-S01-001).

Every response carries ``api_version``.  The schema names are part of the
contract: a breaking change bumps ``API_VERSION`` and the URL prefix.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

API_VERSION = "v1"
ErrorCategory = Literal["INVALID_INPUT", "QUALITY_REJECTED", "MODEL_FAILURE", "MODEL_NOT_READY",
                        "INFRASTRUCTURE_FAILURE", "NOT_FOUND", "CONFLICT"]
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
    details: Dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(_Response):
    error: ErrorBody
    request_id: Optional[str] = None
    analysis: Optional["AnalysisResponse"] = None


class LiveResponse(_Response):
    status: Literal["ALIVE"] = "ALIVE"
    service_version: str


class ReadinessResponse(_Response):
    status: Literal["READY", "NOT_READY"]
    service: Literal["READY"] = "READY"
    model: Literal["READY", "NOT_READY"]
    database: Literal["READY", "NOT_READY"]
    model_version: Optional[str] = None
    schema_version: Optional[int] = None
    detail: Optional[Dict[str, Any]] = None


class ModelInfoResponse(_Response):
    model: Dict[str, Any]
    quality_config: Dict[str, Any]
    measurement_config: Dict[str, Any]
    limitations: List[str]


class CaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identity_status: Literal["VERIFIED", "UNVERIFIED", "UNKNOWN"] = "UNKNOWN"
    external_reference: Optional[str] = Field(default=None, max_length=200)
    label: Optional[str] = Field(default=None, max_length=200)
    data_source: str = Field(default="USER_UPLOAD", max_length=64)


class ExaminationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    captured_at: Optional[datetime] = None
    timestamp_source: Literal["EXIF", "USER_ENTERED", "DEVICE", "UNKNOWN"] = "UNKNOWN"
    notes: Optional[str] = Field(default=None, max_length=2000)


class CaseResponse(_Response):
    case: Dict[str, Any]
    examinations: Optional[List[Dict[str, Any]]] = None


class CaseListResponse(_Response):
    cases: List[Dict[str, Any]]


class ExaminationResponse(_Response):
    examination: Dict[str, Any]
    analyses: Optional[List[Dict[str, Any]]] = None


class AnalysisResponse(_Response):
    schema_name: Literal["AnalysisResponse"] = "AnalysisResponse"
    analysis_id: str
    status: Literal["COMPLETED", "QUALITY_REJECTED", "FAILED"]
    image: Dict[str, Any]
    quality: Dict[str, Any]
    model_version: Optional[str]
    measurement: Optional[Dict[str, Any]]
    inference: Optional[Dict[str, Any]]
    warnings: List[Dict[str, Any]]
    provenance: Dict[str, Any]
    links: Dict[str, str]
    limitation: str


class TrendResponse(_Response):
    trend: Dict[str, Any]


class ComparisonResponse(_Response):
    comparison: Dict[str, Any]


class DeleteResponse(_Response):
    deleted: Dict[str, Any]


ErrorResponse.model_rebuild()
