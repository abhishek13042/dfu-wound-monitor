"""P05-S01 inference API.

Run locally::

    python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000

``create_app`` accepts an already-built engine so tests run against the tiny
fixture model without the 293 MB checkpoint or any external service
(REQ-P05-S01-004).

Error categories (REQ-P05-S01-002), each with a fixed HTTP status:

=========================  ====  ========================================
``INVALID_INPUT``          400   bad request, undecodable/disallowed image
                           413   upload larger than ``max_upload_bytes``
``NOT_FOUND``              404   unknown case/examination/analysis
``UNAUTHENTICATED``        401   v2 route without a valid token
``CONFLICT``               409   write violates an integrity constraint
``QUALITY_REJECTED``       422   the image failed the quality gate
``MODEL_FAILURE``          500   the model failed on an accepted image
``MODEL_NOT_READY``        503   the model artifact is not loaded
``INFRASTRUCTURE_FAILURE`` 503   database/storage/queue unavailable or failing
``BUSY``                   429   too many analyses waiting (``Retry-After``)
=========================  ====  ========================================

Every error body also carries ``failure_class`` (REQ-P06-S02-003): INPUT,
QUALITY, MODEL, PERSISTENCE, or SERVICE (an unexpected server error).

``/api/v1`` has no sign-in and serves the shared ``demo`` workspace, so it and the
dashboard exist only where ``DFU_AUTH_ISSUER`` is unset.  ``/api/v2`` always needs
a token, apart from model information and the signed blob links.

With ``DFU_REDIS_URL`` set the API holds no model: workers do, and it reports the
version they announce.  Without it, the API process runs the jobs itself.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, File, Form, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from src.api import account, analyses_v2, resources, uploads
from src.api.analysis_flow import MEDIA_TYPE, analyse_and_store, analysis_response, parse_calibration
from src.api.auth import TokenVerifier, build_verifier, user_repository
from src.api.errors import ApiError, error_response
from src.api.rendering import decode_mask_png, overlay_png
from src.api.schemas import (
    API_V2,
    API_VERSION,
    AnalysisResponse,
    ErrorResponse,
    LiveResponse,
    ModelInfoResponse,
    ReadinessResponse,
)
from src.api.service import PROJECT_ROOT, ApiSettings, ServiceState
from src.inference.engine import InferenceEngine
from src.inference.pipeline import QUALITY_REJECTED
from src.longitudinal.records import ImageRecord, RecordValidationError
from src.measurement.engine import LIMITATION
from src.preprocessing.decode import decode_image
from src.storage.blobs import LocalBlobStore
from src.storage.database import SCHEMA_VERSION, NotFoundError, StorageError
from src.worker.queue import ArqQueue, JobQueue, LocalQueue
from src.worker.tasks import maintain

SERVICE_VERSION = "p05-1.0"
DASHBOARD_DIR = PROJECT_ROOT / "src" / "dashboard"
LIMITATIONS = [
    "Research prototype. Not a medical device and not clinically validated.",
    "Segmentation was trained and evaluated on FUSeg2021 images only; other cameras, skin tones and wound types "
    "may perform worse.",
    LIMITATION,
    "Trends and comparisons are image-derived technical values, not assessments of healing.",
]
log = logging.getLogger("dfu.api")


def _storage_key(image: ImageRecord) -> str:
    if image.storage_key is None:
        raise ApiError("NOT_FOUND", "IMAGE_NOT_STORED", f"Image {image.image_id} has no stored bytes")
    return image.storage_key


def create_app(settings: ApiSettings | None = None, engine: InferenceEngine | None = None,
               state_factory: Callable[[ApiSettings, InferenceEngine | None], ServiceState] = ServiceState,
               verifier: TokenVerifier | None = None, queue: JobQueue | None = None) -> FastAPI:
    settings = settings or ApiSettings()
    state = state_factory(settings, engine)
    verifier = verifier or build_verifier(settings)
    state.queue = queue or (ArqQueue(settings.redis_url) if settings.redis_url else LocalQueue(state))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if state.engine is None and settings.load_model and not settings.redis_url:
            state.load_model()
        maintenance = asyncio.create_task(maintain(state, state.queue)) if isinstance(state.queue, LocalQueue) else None
        yield
        if maintenance is not None:
            maintenance.cancel()
        await state.queue.close()
        state.db.close()

    app = FastAPI(title="DFU-WoundMonitor API", version=SERVICE_VERSION, lifespan=lifespan,
                  description="Research prototype. Not a medical device.")
    app.state.service = state

    # ----------------------------------------------------------------- errors
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, error: ApiError):
        return error_response(error)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, error: RequestValidationError):
        errors = [{"field": ".".join(str(p) for p in item["loc"]), "message": item["msg"]} for item in error.errors()]
        return error_response(ApiError("INVALID_INPUT", "REQUEST_INVALID", "Request validation failed",
                                        {"errors": errors}))

    @app.exception_handler(RecordValidationError)
    async def _record(_: Request, error: RecordValidationError):
        return error_response(ApiError("INVALID_INPUT", "RECORD_INVALID", str(error), error.to_dict()))

    @app.exception_handler(StorageError)
    async def _storage(_: Request, error: StorageError):
        if isinstance(error, NotFoundError):
            return error_response(ApiError("NOT_FOUND", error.code, error.message))
        if error.code in ("INTEGRITY_VIOLATION", "MODEL_VERSION_CONFLICT"):
            return error_response(ApiError("CONFLICT", error.code, error.message))
        return error_response(ApiError("INFRASTRUCTURE_FAILURE", error.code, error.message))

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, error: Exception):
        log.exception("Unhandled error")
        return error_response(ApiError("INFRASTRUCTURE_FAILURE", "INTERNAL_ERROR",
                                        f"Unexpected server error: {type(error).__name__}"))

    # ----------------------------------------------------------------- health
    @app.get("/health/live", response_model=LiveResponse)
    def live():
        return LiveResponse(service_version=SERVICE_VERSION)

    @app.get("/health/ready", response_model=ReadinessResponse,
             responses={503: {"model": ReadinessResponse}})
    async def ready():
        schema, database_ok, storage_ok = await run_in_threadpool(_dependencies)
        queue_ok = await state.queue.ping()
        model_version = await state.queue.worker_model()
        model_ok = model_version is not None
        body = ReadinessResponse(
            status="READY" if model_ok and database_ok and storage_ok and queue_ok else "NOT_READY",
            model="READY" if model_ok else "NOT_READY", database="READY" if database_ok else "NOT_READY",
            storage="READY" if storage_ok else "NOT_READY", queue="READY" if queue_ok else "NOT_READY",
            model_version=model_version, schema_version=schema,
            detail=None if model_ok else {"model_error": state.model_error},
        )
        return JSONResponse(body.model_dump(mode="json"), status_code=200 if body.status == "READY" else 503)

    def _dependencies() -> tuple[int | None, bool, bool]:
        schema = None
        try:
            schema = state.db.schema_version()
            database_ok = state.db.ping() and schema == SCHEMA_VERSION
            state.ensure_registered()
        except Exception:  # noqa: BLE001 - readiness must never raise
            database_ok = False
        try:
            storage_ok = state.storage_ready()
        except Exception:  # noqa: BLE001 - readiness must never raise
            storage_ok = False
        return schema, database_ok, storage_ok

    # ----------------------------------------------------------------- model
    async def describe_model(version: str) -> ModelInfoResponse:
        if settings.redis_url and state.pipeline is None:
            model_version = await state.queue.worker_model()
            if model_version is None:
                state.require_pipeline()
            model = await run_in_threadpool(state.db.get_model, model_version)
        else:
            model = state.require_pipeline().engine.describe()
        return ModelInfoResponse(api_version=version, model=model,
                                 quality_config=state.gate.config.reference(),
                                 measurement_config=state.measurement_config.reference(), limitations=LIMITATIONS)

    @app.get(f"/api/{API_V2}/model", response_model=ModelInfoResponse)
    async def model_info_v2():
        return await describe_model(API_V2)

    # ----------------------------------------------------------------- v2
    current_user = user_repository(state, verifier)
    app.include_router(resources.router(state, API_V2, current_user))
    app.include_router(uploads.router(state, current_user))
    app.include_router(analyses_v2.router(state, current_user))
    app.include_router(account.router(state, current_user))
    if isinstance(state.blobs, LocalBlobStore):
        app.include_router(uploads.local_blob_router(state.blobs, settings.max_upload_bytes))

    if settings.auth_issuer:  # REQ-P07-S04: v1 cannot run beside real accounts
        return app

    # ----------------------------------------------------------------- v1 demo
    demo = APIRouter(prefix=f"/api/{API_VERSION}")

    @demo.get("/model", response_model=ModelInfoResponse)
    async def model_info():
        return await describe_model(API_VERSION)

    @demo.post("/analyses", response_model=AnalysisResponse, status_code=201,
               responses={code: {"model": ErrorResponse} for code in (400, 404, 413, 422, 500, 503)})
    def analyze(
        file: UploadFile = File(...),
        examination_id: str | None = Form(None),
        pixels_per_mm: float | None = Form(None),
        calibration_method: str | None = Form(None),
        calibration_source: str | None = Form(None),
        threshold: float | None = Form(None),
    ):
        state.require_pipeline()
        data = file.file.read(settings.max_upload_bytes + 1)
        if len(data) > settings.max_upload_bytes:
            raise ApiError("INVALID_INPUT", "INPUT_TOO_LARGE",
                           f"Upload exceeds {settings.max_upload_bytes} bytes", status=413)
        if examination_id:
            state.db.get_examination(examination_id)
        calibration = parse_calibration(pixels_per_mm, calibration_method, calibration_source)
        stored = analyse_and_store(state, data, filename=file.filename, examination_id=examination_id,
                                   calibration=calibration, threshold=threshold)
        record, failure = stored.record, stored.failure
        response = analysis_response(record, stored.image.to_dict())
        if failure is not None:
            raise ApiError("MODEL_FAILURE", failure.code, failure.message, failure.details, analysis=response)
        if record.status == QUALITY_REJECTED:
            raise ApiError("QUALITY_REJECTED", "QUALITY_REJECTED",
                           "Image rejected by the quality gate: " + ", ".join(record.quality["reason_codes"]),
                           {"reason_codes": record.quality["reason_codes"]}, analysis=response)
        return response

    @demo.get("/analyses/{analysis_id}/image")
    def get_image(analysis_id: str):
        image = state.db.get_image(state.db.get_analysis(analysis_id).image_id)
        return Response(state.blobs.get(_storage_key(image)), media_type=MEDIA_TYPE.get(image.format))

    @demo.get("/analyses/{analysis_id}/mask.png")
    def get_mask(analysis_id: str):
        return Response(state.blobs.get(state.db.get_artifact(analysis_id, "MASK")["storage_key"]),
                        media_type="image/png")

    @demo.get("/analyses/{analysis_id}/probability.png")
    def get_probability(analysis_id: str):
        return Response(state.blobs.get(state.db.get_artifact(analysis_id, "PROBABILITY")["storage_key"]),
                        media_type="image/png")

    @demo.get("/analyses/{analysis_id}/overlay.png")
    def get_overlay(analysis_id: str, max_side: int = Query(1024, ge=64, le=8192)):
        record = state.db.get_analysis(analysis_id)
        image = state.db.get_image(record.image_id)
        mask = decode_mask_png(state.blobs.get(state.db.get_artifact(analysis_id, "MASK")["storage_key"]))
        decoded = decode_image(state.blobs.get(_storage_key(image)))
        return Response(overlay_png(decoded.image, mask, max_side), media_type="image/png")

    app.include_router(demo)
    app.include_router(resources.router(state, API_VERSION, lambda: state.db))

    # ----------------------------------------------------------------- dashboard
    if DASHBOARD_DIR.is_dir():
        app.mount("/dashboard", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse("/dashboard/")

    return app


def _default_app() -> FastAPI:
    return create_app()


def __getattr__(name: str):  # lazily build ``app`` for ``uvicorn src.api.app:app``
    if name == "app":
        return _default_app()
    raise AttributeError(name)
