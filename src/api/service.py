"""Service configuration and the objects shared by every route.

The worker builds the same ``ServiceState``, so an analysis stored by a queued
job goes through exactly the code an API request uses.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.api.errors import ApiError
from src.inference.engine import DEFAULT_INFERENCE_CONFIG, InferenceEngine
from src.inference.errors import InferenceError
from src.inference.pipeline import AnalysisPipeline
from src.measurement.engine import MeasurementConfig
from src.quality.gate import QualityGate
from src.storage.blobs import create_blob_store
from src.storage.database import StorageError
from src.storage.repository import Repository

PROJECT_ROOT = Path(__file__).resolve().parents[2]
log = logging.getLogger("dfu.api")


@dataclass
class ApiSettings:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("DFU_DATA_DIR", PROJECT_ROOT / "runtime")))
    inference_config: Path = field(default_factory=lambda: Path(os.environ.get("DFU_INFERENCE_CONFIG",
                                                                               DEFAULT_INFERENCE_CONFIG)))
    max_upload_bytes: int = 25 * 1024 * 1024
    load_model: bool = True
    database_url: str | None = field(default_factory=lambda: os.environ.get("DFU_DATABASE_URL"))
    storage_backend: str = field(default_factory=lambda: os.environ.get("DFU_STORAGE_BACKEND", "local"))
    s3_bucket: str | None = field(default_factory=lambda: os.environ.get("DFU_S3_BUCKET"))
    s3_endpoint: str | None = field(default_factory=lambda: os.environ.get("DFU_S3_ENDPOINT"))
    auth_issuer: str | None = field(default_factory=lambda: os.environ.get("DFU_AUTH_ISSUER"))
    auth_audience: str | None = field(default_factory=lambda: os.environ.get("DFU_AUTH_AUDIENCE"))
    auth_jwks_url: str | None = field(default_factory=lambda: os.environ.get("DFU_AUTH_JWKS_URL"))
    redis_url: str | None = field(default_factory=lambda: os.environ.get("DFU_REDIS_URL"))
    max_queue_depth: int = field(default_factory=lambda: int(os.environ.get("DFU_MAX_QUEUE", "100")))


class ServiceState:
    def __init__(self, settings: ApiSettings, engine: InferenceEngine | None) -> None:
        self.settings = settings
        self.db = Repository(settings.database_url or settings.data_dir / "dfu_wound_monitor.sqlite3")
        self.blobs = create_blob_store(settings.storage_backend, settings.data_dir, settings.s3_bucket,
                                       settings.s3_endpoint)
        self.gate = QualityGate()
        self.measurement_config = MeasurementConfig.load()
        self.engine = engine
        self.pipeline: AnalysisPipeline | None = None
        self.model_error: dict[str, Any] | None = None
        self.registered = False
        self.storage_private = False
        self.queue: Any = None  # set by create_app; the worker passes its queue to run_job
        self.lock = threading.Lock()
        if engine is not None:
            self._attach(engine)

    def _attach(self, engine: InferenceEngine) -> None:
        self.engine = engine
        self.pipeline = AnalysisPipeline(engine, self.gate, self.measurement_config)
        try:
            self.ensure_registered()
        except StorageError as error:
            if error.code == "MODEL_VERSION_CONFLICT":
                raise
            # PostgreSQL may be down or not yet migrated.  The model is still
            # usable, so registration is retried by the next request.
            log.warning("Model not registered yet: %s", error.code)

    def ensure_registered(self) -> None:
        if self.engine is not None and not self.registered:
            self.db.register_model(self.engine.describe())
            self.registered = True

    def storage_ready(self) -> bool:
        """Reachable and private.  A public bucket keeps the service out of rotation."""

        if not self.blobs.ping():
            return False
        if not self.storage_private:
            self.blobs.ensure_private()
            self.storage_private = True
        return True

    def load_model(self) -> None:
        try:
            self._attach(InferenceEngine.from_config(self.settings.inference_config))
            self.model_error = None
        except InferenceError as error:
            self.model_error = error.to_dict()
            log.error("Model not ready: %s", error)

    def require_pipeline(self) -> AnalysisPipeline:
        if self.pipeline is None:
            raise ApiError("MODEL_NOT_READY", "MODEL_NOT_LOADED", "The segmentation model is not loaded",
                           {"model_error": self.model_error})
        self.ensure_registered()
        return self.pipeline
