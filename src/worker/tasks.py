"""Run one analysis job, and keep the job table honest.

``process_job`` is plain Python.  The queue only decides when it runs, so its
behaviour can be tested without Redis, and a job on a laptop takes the same path
as a job in production.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from src.api.analysis_flow import analyse_and_store, parse_calibration
from src.api.errors import ApiError
from src.api.service import ServiceState
from src.storage.database import NotFoundError
from src.storage.repository import Repository
from src.worker.queue import JobQueue, QueueUnavailable
from src.worker.state import FAILED, QUEUED, RUNNING

log = logging.getLogger("dfu.worker")

MAX_RETRIES = 3                  # REQ-P07-S05-004
BACKOFF_SECONDS = (5, 20, 60)
RETRYABLE_CATEGORIES = {"INFRASTRUCTURE_FAILURE", "MODEL_NOT_READY"}
JOB_TIMEOUT_SECONDS = 300
RUNNING_TIMEOUT_SECONDS = 600    # longer than a job can run, so a slow job is never taken for a lost one
QUEUED_TIMEOUT_SECONDS = 300     # a message lost by Redis, or a retry that could not be re-queued
SWEEP_SECONDS = 60


@dataclass(frozen=True)
class JobResult:
    status: str | None                 # None: this delivery had nothing to do
    retry_attempt: int | None = None
    retry_in: float = 0


def _error(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _retry(state: ServiceState, job: dict[str, Any], error: dict[str, str]) -> JobResult:
    attempts = job["attempts"]  # the claim already counted this one
    if attempts > MAX_RETRIES:
        return _fail(state, job, error)
    if not state.db.move_job(job["analysis_id"], RUNNING, QUEUED, error=error):
        return JobResult(None)  # the user or the case was deleted while it ran
    return JobResult(QUEUED, attempts, BACKOFF_SECONDS[attempts - 1])


def _fail(state: ServiceState, job: dict[str, Any], error: dict[str, str]) -> JobResult:
    if not state.db.move_job(job["analysis_id"], RUNNING, FAILED, error=error):
        return JobResult(None)
    # No result holds the image, so the expiry sweep may remove it.
    state.db.for_owner(job["owner_id"]).extend_upload(job["upload_id"], datetime.now(UTC).isoformat())
    return JobResult(FAILED)


def _finish(state: ServiceState, db: Repository, job: dict[str, Any], status: str) -> JobResult:
    moved = state.db.move_job(job["analysis_id"], RUNNING, status)
    db.delete_upload(job["upload_id"])
    return JobResult(status if moved else None)


def process_job(state: ServiceState, analysis_id: str) -> JobResult:
    job = state.db.claim_job(analysis_id)
    if job is None:
        return JobResult(None)  # redelivered, already finished, or its owner has gone
    db = state.db.for_owner(job["owner_id"])
    saved = state.db.analysis_status(analysis_id)
    if saved is not None:  # an earlier worker died after saving the result and before finishing the job
        return _finish(state, db, job, saved)
    request = job["request"]
    try:
        upload = db.get_upload(job["upload_id"])
        calibration = parse_calibration(request.get("pixels_per_mm"), request.get("calibration_method"),
                                        request.get("calibration_source"))
        stored = analyse_and_store(state, state.blobs.get(upload["storage_key"]), filename=upload["filename"],
                                   examination_id=job["examination_id"], calibration=calibration,
                                   threshold=request.get("threshold"), analysis_id=analysis_id, db=db)
    except ApiError as error:
        failure = _error(error.body.code, error.body.message)
        return _retry(state, job, failure) if error.body.category in RETRYABLE_CATEGORIES else _fail(state, job, failure)
    except NotFoundError as error:
        return _fail(state, job, _error(error.code, error.message))
    except Exception as error:  # noqa: BLE001 - an unknown failure is treated as infrastructure and retried
        log.warning("Job %s attempt %s failed: %s", analysis_id, job["attempts"], type(error).__name__)
        return _retry(state, job, _error("WORKER_ERROR", f"The job failed with {type(error).__name__}"))
    return _finish(state, db, job, stored.record.status)


async def run_job(state: ServiceState, queue: JobQueue, analysis_id: str) -> JobResult:
    result = await asyncio.to_thread(process_job, state, analysis_id)
    if result.retry_attempt is not None:
        try:
            await queue.enqueue(analysis_id, result.retry_attempt, result.retry_in)
        except QueueUnavailable:
            log.warning("Retry of %s not queued; the sweep will pick it up", analysis_id)
    return result


def sweep(state: ServiceState) -> list[tuple[str, int]]:
    """Recover what a dead worker or a lost message left behind.  Returns the jobs to queue again."""

    now = datetime.now(UTC)
    again: list[tuple[str, int]] = []
    for job in state.db.overdue_jobs(RUNNING, (now - timedelta(seconds=RUNNING_TIMEOUT_SECONDS)).isoformat()):
        if job["requeued"]:
            _fail(state, job, _error("WORKER_LOST", "The worker stopped twice while running this job"))
        elif state.db.move_job(job["analysis_id"], RUNNING, QUEUED, requeued=1):
            again.append((job["analysis_id"], job["attempts"]))
    for job in state.db.overdue_jobs(QUEUED, (now - timedelta(seconds=QUEUED_TIMEOUT_SECONDS)).isoformat()):
        again.append((job["analysis_id"], job["attempts"]))
    state.db.expire_uploads(state.blobs)
    return again


async def maintain(state: ServiceState, queue: JobQueue, beat: Any = None) -> None:
    """Runs for the life of a worker.  It is a task and not an arq job, so a running job cannot delay it."""

    since_sweep = SWEEP_SECONDS
    while True:
        try:
            if beat is not None:
                await beat()
            if since_sweep >= SWEEP_SECONDS:
                since_sweep = 0
                for analysis_id, attempt in await asyncio.to_thread(sweep, state):
                    await queue.enqueue(analysis_id, attempt)
        except Exception as error:  # noqa: BLE001 - the next pass tries again
            log.warning("Maintenance pass failed: %s", type(error).__name__)
        await asyncio.sleep(20)
        since_sweep += 20
