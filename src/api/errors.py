"""The API's one error type and its mapping to HTTP status and failure class."""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

from src.api.schemas import AnalysisResponse, ErrorBody, ErrorCategory, ErrorResponse, FailureClass
from src.observability.context import HEADER, current_request_id
from src.observability.metrics import record_error

STATUS: dict[ErrorCategory, int] = {
    "INVALID_INPUT": 400, "NOT_FOUND": 404, "CONFLICT": 409, "QUALITY_REJECTED": 422, "MODEL_FAILURE": 500,
    "MODEL_NOT_READY": 503, "INFRASTRUCTURE_FAILURE": 503, "UNAUTHENTICATED": 401, "BUSY": 429,
}
FAILURE_CLASS: dict[ErrorCategory, FailureClass] = {
    "INVALID_INPUT": "INPUT", "NOT_FOUND": "INPUT", "QUALITY_REJECTED": "QUALITY", "MODEL_FAILURE": "MODEL",
    "MODEL_NOT_READY": "MODEL", "CONFLICT": "PERSISTENCE", "INFRASTRUCTURE_FAILURE": "PERSISTENCE",
    "UNAUTHENTICATED": "INPUT", "BUSY": "SERVICE",
}


class ApiError(Exception):
    def __init__(self, category: ErrorCategory, code: str, message: str, details: dict[str, Any] | None = None,
                 status: int | None = None, analysis: AnalysisResponse | None = None) -> None:
        super().__init__(message)
        failure_class: FailureClass = "SERVICE" if code == "INTERNAL_ERROR" else FAILURE_CLASS[category]
        self.body = ErrorBody(category=category, failure_class=failure_class, code=code, message=message,
                              details=details or {})
        self.status = status or STATUS[category]
        self.analysis = analysis


def error_response(error: ApiError, request_id: str | None = None) -> JSONResponse:
    # REQ-P10-S01-001: the body names the same ID as the X-Request-ID header and the logs.
    request_id = request_id or current_request_id()
    record_error(error.body.failure_class, error.body.category)
    payload = ErrorResponse(error=error.body, request_id=request_id, analysis=error.analysis)
    headers = {"WWW-Authenticate": "Bearer"} if error.status == 401 else {}
    if error.status == 429:
        headers = {"Retry-After": str(error.body.details["retry_after_seconds"])}
    if request_id:
        headers[HEADER] = request_id  # the 500 handler's response bypasses the middleware's header
    return JSONResponse(payload.model_dump(mode="json"), status_code=error.status, headers=headers or None)
