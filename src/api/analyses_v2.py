"""P07-S05 analysis jobs: submission returns at once, and a worker does the rest.

The order at submit is what keeps an outage clean: the queue is checked first,
the row is written, and the message follows.  If the message cannot be sent, the
row is removed, so nothing is left waiting for a worker that will never hear of it.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict

from src.api.analysis_flow import analysis_response, parse_calibration
from src.api.errors import ApiError
from src.api.schemas import API_V2, AnalysisResponse
from src.api.service import ServiceState
from src.api.uploads import live_upload
from src.longitudinal.records import new_id
from src.storage.database import StorageError
from src.storage.repository import Repository
from src.worker.queue import QueueUnavailable
from src.worker.state import ACTIVE

UPLOAD_HOLD_SECONDS = 24 * 3600  # a waiting job keeps its image from the expiry sweep
RETRY_AFTER_SECONDS = 30


class AnalysisCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    upload_id: str
    examination_id: str | None = None
    pixels_per_mm: float | None = None
    calibration_method: str | None = None
    calibration_source: str | None = None
    threshold: float | None = None


class JobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_version: str = API_V2
    analysis_id: str
    status: str
    error: dict[str, Any] | None = None
    links: dict[str, str]


def job_response(job: dict[str, Any]) -> JobResponse:
    return JobResponse(analysis_id=job["analysis_id"], status=job["status"], error=job["error"],
                       links={"self": f"/api/{API_V2}/analyses/{job['analysis_id']}"})


def _queue_down() -> ApiError:
    return ApiError("INFRASTRUCTURE_FAILURE", "QUEUE_UNAVAILABLE", "The analysis queue is unavailable")


def _prepare(state: ServiceState, db: Repository, body: AnalysisCreate) -> dict[str, Any]:
    """Everything before the queue.  An existing job for this upload is returned, not repeated."""

    existing = db.job_for_upload(body.upload_id)
    if existing is not None:
        return existing
    upload = live_upload(db, body.upload_id)
    if upload["status"] != "VERIFIED":
        raise ApiError("CONFLICT", "UPLOAD_NOT_VERIFIED", "Verify the upload before analysing it")
    if body.examination_id:
        db.get_examination(body.examination_id)
    parse_calibration(body.pixels_per_mm, body.calibration_method, body.calibration_source)
    request = body.model_dump(exclude={"upload_id", "examination_id"}, exclude_none=True)
    try:
        job = db.add_job(new_id("ana"), body.upload_id, body.examination_id, request)
    except StorageError as error:
        if error.code != "INTEGRITY_VIOLATION":
            raise
        # A double-click reached the unique constraint, or the examination has just gone.
        existing = db.job_for_upload(body.upload_id)
        if existing is None:
            raise
        return existing
    db.extend_upload(body.upload_id, (datetime.now(UTC) + timedelta(seconds=UPLOAD_HOLD_SECONDS)).isoformat())
    return job


def router(state: ServiceState, current_repository: Callable[..., Repository]) -> APIRouter:
    routes = APIRouter(prefix=f"/api/{API_V2}")

    @routes.post("/analyses", response_model=JobResponse, status_code=202)
    async def submit(body: AnalysisCreate, db: Repository = Depends(current_repository)):
        try:
            waiting = await state.queue.depth()
        except QueueUnavailable as error:
            raise _queue_down() from error
        if waiting >= state.settings.max_queue_depth:
            raise ApiError("BUSY", "QUEUE_FULL", "Too many analyses are waiting; try again shortly",
                           {"retry_after_seconds": RETRY_AFTER_SECONDS})
        if await state.queue.worker_model() is None:
            state.require_pipeline()  # nothing can run a job, so none is accepted
        job = await run_in_threadpool(_prepare, state, db, body)
        if job["attempts"] == 0 and job["status"] == "QUEUED":
            try:
                await state.queue.enqueue(job["analysis_id"])
            except QueueUnavailable as error:
                await run_in_threadpool(db.delete_job, job["analysis_id"])
                raise _queue_down() from error
        return job_response(job)

    @routes.get("/analyses/{analysis_id}", response_model=AnalysisResponse | JobResponse)
    def get_analysis(analysis_id: str, db: Repository = Depends(current_repository)):
        job = db.find_job(analysis_id)
        if job is not None and (job["status"] in ACTIVE or not db.has_analysis(analysis_id)):
            return job_response(job)
        record = db.get_analysis(analysis_id)
        return analysis_response(record, db.get_image(record.image_id).to_dict(), API_V2)

    return routes
