"""Where analysis jobs wait.

``ArqQueue`` is the real one.  ``LocalQueue`` runs jobs in the API process, for a
laptop or a demo with no Redis, through the same ``run_job`` the worker uses.
The database row is the truth about a job.  A queue message only says "look at
this ID", so a lost or repeated message cannot change a result.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Protocol

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from redis.exceptions import RedisError

log = logging.getLogger("dfu.worker")

JOB_FUNCTION = "run_analysis"
HEARTBEAT_KEY = "dfu:worker"
HEARTBEAT_SECONDS = 60
QUEUE_TIMEOUT_SECONDS = 2


class QueueUnavailable(Exception):
    pass


class JobQueue(Protocol):
    async def enqueue(self, analysis_id: str, attempt: int = 0, defer_seconds: float = 0) -> None: ...

    async def depth(self) -> int: ...

    async def ping(self) -> bool: ...

    async def worker_model(self) -> str | None: ...

    async def close(self) -> None: ...


class ArqQueue:
    def __init__(self, url: str) -> None:
        self.settings = RedisSettings.from_dsn(url)
        self.settings.conn_retries = 0
        self.settings.conn_timeout = QUEUE_TIMEOUT_SECONDS
        self._pool: ArqRedis | None = None

    async def _redis(self) -> ArqRedis:
        if self._pool is None:
            self._pool = await create_pool(self.settings)
        return self._pool

    async def _call(self, action: Any) -> Any:
        try:
            return await asyncio.wait_for(action(await self._redis()), QUEUE_TIMEOUT_SECONDS)
        except (RedisError, OSError, TimeoutError) as error:
            raise QueueUnavailable(type(error).__name__) from error

    async def enqueue(self, analysis_id: str, attempt: int = 0, defer_seconds: float = 0) -> None:
        # The attempt is in the job ID, because arq ignores an ID it still remembers.
        await self._call(lambda redis: redis.enqueue_job(JOB_FUNCTION, analysis_id, _job_id=f"{analysis_id}:{attempt}",
                                                         _defer_by=defer_seconds or None))

    async def depth(self) -> int:
        return await self._call(lambda redis: redis.zcard(redis.default_queue_name))

    async def ping(self) -> bool:
        try:
            return bool(await self._call(lambda redis: redis.ping()))
        except QueueUnavailable:
            return False

    async def worker_model(self) -> str | None:
        try:
            raw = await self._call(lambda redis: redis.get(HEARTBEAT_KEY))
        except QueueUnavailable:
            return None
        return json.loads(raw)["model_version"] if raw else None

    async def heartbeat(self, model_version: str) -> None:
        payload = json.dumps({"model_version": model_version})
        await self._call(lambda redis: redis.set(HEARTBEAT_KEY, payload, ex=HEARTBEAT_SECONDS))

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.aclose()
            self._pool = None


class LocalQueue:
    """Jobs run one at a time inside the API process."""

    def __init__(self, state: Any) -> None:
        self.state = state
        self._waiting = 0
        self._tasks: set[asyncio.Task[None]] = set()
        self._turn: asyncio.Lock | None = None

    async def enqueue(self, analysis_id: str, attempt: int = 0, defer_seconds: float = 0) -> None:
        self._turn = self._turn or asyncio.Lock()
        self._waiting += 1
        task = asyncio.create_task(self._run(analysis_id, defer_seconds))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run(self, analysis_id: str, defer_seconds: float) -> None:
        from src.worker.tasks import run_job

        assert self._turn is not None
        try:
            if defer_seconds:
                await asyncio.sleep(defer_seconds)
            async with self._turn:
                await run_job(self.state, self, analysis_id)
        except Exception:  # noqa: BLE001 - the job row stays QUEUED or RUNNING for the sweep
            log.exception("Local job failed: %s", analysis_id)
        finally:
            self._waiting -= 1

    async def depth(self) -> int:
        return self._waiting

    async def ping(self) -> bool:
        return True

    async def worker_model(self) -> str | None:
        pipeline = self.state.pipeline
        return pipeline.engine.config.model_version if pipeline is not None else None

    async def close(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
