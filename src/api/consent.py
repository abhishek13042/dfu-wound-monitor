"""P10-S03 consent and the per-case keep choice.

A user accepts one version of the consent text before their first upload
(REQ-P10-S03-003); changing the text means a new ``CONSENT_VERSION``, and
everyone accepts again.  A case marked kept is left out of retention
(REQ-P10-S03-001).
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from src.api.errors import ApiError
from src.api.schemas import API_V2
from src.api.service import ServiceState
from src.storage.repository import Repository

CONSENT_VERSION = "2026-11-v1"


class ConsentAccept(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text_version: str


class ConsentResponse(BaseModel):
    text_version: str
    accepted_at: str | None
    retention_hours: int


class KeepUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keep: bool


class KeepResponse(BaseModel):
    case_id: str
    keep: bool
    retention_hours: int


def require_consent(db: Repository) -> None:
    if db.consent_time(CONSENT_VERSION) is None:
        raise ApiError("INVALID_INPUT", "CONSENT_REQUIRED",
                       "Accept the current consent text before uploading", {"text_version": CONSENT_VERSION},
                       status=403)


def router(state: ServiceState, current_repository: Callable[..., Repository]) -> APIRouter:
    routes = APIRouter(prefix=f"/api/{API_V2}")
    hours = state.settings.retention_hours

    @routes.get("/consent", response_model=ConsentResponse)
    def get_consent(db: Repository = Depends(current_repository)):
        return ConsentResponse(text_version=CONSENT_VERSION, accepted_at=db.consent_time(CONSENT_VERSION),
                               retention_hours=hours)

    @routes.post("/consent", response_model=ConsentResponse)
    def accept_consent(body: ConsentAccept, db: Repository = Depends(current_repository)):
        if body.text_version != CONSENT_VERSION:
            raise ApiError("CONFLICT", "CONSENT_VERSION_CHANGED", "The consent text has changed; read it again",
                           {"text_version": CONSENT_VERSION})
        return ConsentResponse(text_version=CONSENT_VERSION, accepted_at=db.record_consent(CONSENT_VERSION),
                               retention_hours=hours)

    @routes.get("/cases/{case_id}/keep", response_model=KeepResponse)
    def get_keep(case_id: str, db: Repository = Depends(current_repository)):
        return KeepResponse(case_id=case_id, keep=db.case_kept(case_id), retention_hours=hours)

    @routes.put("/cases/{case_id}/keep", response_model=KeepResponse)
    def set_keep(case_id: str, body: KeepUpdate, db: Repository = Depends(current_repository)):
        return KeepResponse(case_id=case_id, keep=db.set_case_keep(case_id, body.keep), retention_hours=hours)

    return routes
