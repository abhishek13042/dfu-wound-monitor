"""arq entry point: ``python -m arq src.worker.settings.WorkerSettings``.

A worker holds one model and takes one job at a time.  If the model cannot be
loaded and verified, ``on_startup`` raises, so the process takes no jobs and no
heartbeat appears (the model's SHA-256 is checked by ``InferenceEngine``).
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

from arq.connections import RedisSettings

from src.api.service import ApiSettings, ServiceState
from src.worker.queue import ArqQueue
from src.worker.tasks import JOB_TIMEOUT_SECONDS, maintain, run_job

REDIS_URL = os.environ.get("DFU_REDIS_URL", "redis://127.0.0.1:6379")


def build_state(settings: ApiSettings | None = None) -> ServiceState:
    state = ServiceState(settings or ApiSettings(), None)
    state.load_model()
    if state.pipeline is None:
        raise RuntimeError(f"Worker refuses to start without a verified model: {state.model_error}")
    return state


async def on_startup(ctx: dict[str, Any]) -> None:
    state = ctx.setdefault("state", None) or build_state()
    ctx["state"] = state
    queue = ctx["queue"] = ArqQueue(state.settings.redis_url or REDIS_URL)
    assert state.pipeline is not None
    model_version = state.pipeline.engine.config.model_version
    ctx["maintenance"] = asyncio.create_task(maintain(state, queue, lambda: queue.heartbeat(model_version)))


async def on_shutdown(ctx: dict[str, Any]) -> None:
    ctx["maintenance"].cancel()
    await ctx["queue"].close()


async def run_analysis(ctx: dict[str, Any], analysis_id: str) -> str | None:
    return (await run_job(ctx["state"], ctx["queue"], analysis_id)).status


class WorkerSettings:
    functions = [run_analysis]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
    max_jobs = 1
    job_timeout = JOB_TIMEOUT_SECONDS
    keep_result = 0
    max_tries = 1  # retries are decided by process_job, and recorded on the job row
    handle_signals = sys.platform != "win32"  # asyncio has no signal handlers on Windows
