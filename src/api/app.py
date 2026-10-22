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
``CONFLICT``               409   write violates an integrity constraint
``QUALITY_REJECTED``       422   the image failed the quality gate
``MODEL_FAILURE``          500   the model failed on an accepted image
``MODEL_NOT_READY``        503   the model artifact is not loaded
``INFRASTRUCTURE_FAILURE`` 503   database/storage unavailable or failing
=========================  ====  ========================================

Every error body also carries ``failure_class`` (REQ-P06-S02-003): INPUT,
QUALITY, MODEL, PERSISTENCE, or SERVICE (an unexpected server error).
"""

from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from src.api.rendering import decode_mask_png, mask_png, overlay_png, probability_png
from src.api.schemas import (
    API_VERSION,
    AnalysisResponse,
    CaseCreate,
    CaseListResponse,
    CaseResponse,
    ComparisonResponse,
    DeleteResponse,
    ErrorBody,
    ErrorResponse,
    ExaminationCreate,
    ExaminationResponse,
    LiveResponse,
    ModelInfoResponse,
    ReadinessResponse,
    TrendResponse,
)
from src.inference.engine import DEFAULT_INFERENCE_CONFIG, InferenceEngine
from src.inference.errors import InferenceError, InputError, InputTooLargeError
from src.inference.pipeline import COMPLETED, QUALITY_REJECTED, AnalysisPipeline
from src.longitudinal.comparison import CompatibilityPolicy, MeasurementPoint, compare
from src.longitudinal.records import (
    AnalysisRecord,
    CaseRecord,
    ExaminationRecord,
    ImageRecord,
    RecordValidationError,
    analysis_record_from_outcome,
    image_record_from_outcome,
    new_id,
)
from src.longitudinal.trends import build_trend
from src.measurement.engine import LIMITATION, Calibration, MeasurementConfig, MeasurementError
from src.preprocessing.decode import decode_image
from src.quality.gate import QualityGate
from src.storage.database import BlobStore, Database, NotFoundError, StorageError

SERVICE_VERSION = "p05-1.0"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = PROJECT_ROOT / "src" / "dashboard"
LIMITATIONS = [
    "Research prototype. Not a medical device and not clinically validated.",
    "Segmentation was trained and evaluated on FUSeg2021 images only; other cameras, skin tones and wound types "
    "may perform worse.",
    LIMITATION,
    "Trends and comparisons are image-derived technical values, not assessments of healing.",
]
STATUS = {"INVALID_INPUT": 400, "NOT_FOUND": 404, "CONFLICT": 409, "QUALITY_REJECTED": 422, "MODEL_FAILURE": 500,
          "MODEL_NOT_READY": 503, "INFRASTRUCTURE_FAILURE": 503}
FAILURE_CLASS = {"INVALID_INPUT": "INPUT", "NOT_FOUND": "INPUT", "QUALITY_REJECTED": "QUALITY",
                 "MODEL_FAILURE": "MODEL", "MODEL_NOT_READY": "MODEL", "CONFLICT": "PERSISTENCE",
                 "INFRASTRUCTURE_FAILURE": "PERSISTENCE"}
FORMAT_SUFFIX = {"PNG": ".png", "JPEG": ".jpg", "BMP": ".bmp", "TIFF": ".tif", "WEBP": ".webp"}
MEDIA_TYPE = {"PNG": "image/png", "JPEG": "image/jpeg", "BMP": "image/bmp", "TIFF": "image/tiff", "WEBP": "image/webp"}
log = logging.getLogger("dfu.api")


@dataclass
class ApiSettings:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("DFU_DATA_DIR", PROJECT_ROOT / "runtime")))
    inference_config: Path = field(default_factory=lambda: Path(os.environ.get("DFU_INFERENCE_CONFIG",
                                                                               DEFAULT_INFERENCE_CONFIG)))
    max_upload_bytes: int = 25 * 1024 * 1024
    load_model: bool = True


class ApiError(Exception):
    def __init__(self, category: str, code: str, message: str, details: Optional[Dict[str, Any]] = None,
                 status: Optional[int] = None, analysis: Optional[AnalysisResponse] = None) -> None:
        super().__init__(message)
        failure_class = "SERVICE" if code == "INTERNAL_ERROR" else FAILURE_CLASS[category]
        self.body = ErrorBody(category=category, failure_class=failure_class, code=code, message=message,
                              details=details or {})
        self.status = status or STATUS[category]
        self.analysis = analysis


def _error_response(error: ApiError, request_id: Optional[str] = None) -> JSONResponse:
    payload = ErrorResponse(error=error.body, request_id=request_id, analysis=error.analysis)
    return JSONResponse(payload.model_dump(mode="json"), status_code=error.status)


class ServiceState:
    def __init__(self, settings: ApiSettings, engine: Optional[InferenceEngine]) -> None:
        self.settings = settings
        self.db = Database(settings.data_dir / "dfu_wound_monitor.sqlite3")
        self.blobs = BlobStore(settings.data_dir / "blobs")
        self.gate = QualityGate()
        self.measurement_config = MeasurementConfig.load()
        self.engine = engine
        self.pipeline: Optional[AnalysisPipeline] = None
        self.model_error: Optional[Dict[str, Any]] = None
        self.lock = threading.Lock()
        if engine is not None:
            self._attach(engine)

    def _attach(self, engine: InferenceEngine) -> None:
        self.engine = engine
        self.pipeline = AnalysisPipeline(engine, self.gate, self.measurement_config)
        description = engine.describe()
        self.db.register_model(description)

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
        return self.pipeline


def _analysis_response(record: AnalysisRecord, image: Dict[str, Any]) -> AnalysisResponse:
    base = f"/api/{API_VERSION}/analyses/{record.analysis_id}"
    links = {"self": base, "image": f"{base}/image"}
    if record.status == COMPLETED:
        links.update(mask=f"{base}/mask.png", overlay=f"{base}/overlay.png", probability=f"{base}/probability.png")
    return AnalysisResponse(analysis_id=record.analysis_id, status=record.status, image=image,
                            quality=record.quality, model_version=record.model_version,
                            measurement=record.measurement, inference=record.inference_summary,
                            warnings=record.warnings, provenance=record.provenance, links=links,
                            limitation=LIMITATION)


def _point(state: ServiceState, analysis: AnalysisRecord) -> MeasurementPoint:
    if analysis.examination_id is None:
        examination = ExaminationRecord.create(examination_id=f"unlinked-{analysis.analysis_id}")
    else:
        examination = state.db.get_examination(analysis.examination_id)
    if examination.case_id is None:
        case = CaseRecord.create(case_id="case-unknown")
    else:
        case = state.db.get_case(examination.case_id)
    return MeasurementPoint(case, examination, analysis)


def create_app(settings: Optional[ApiSettings] = None, engine: Optional[InferenceEngine] = None,
               state_factory: Callable[[ApiSettings, Optional[InferenceEngine]], ServiceState] = ServiceState) -> FastAPI:
    settings = settings or ApiSettings()
    state = state_factory(settings, engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if state.engine is None and settings.load_model:
            state.load_model()
        yield
        state.db.close()

    app = FastAPI(title="DFU-WoundMonitor API", version=SERVICE_VERSION, lifespan=lifespan,
                  description="Research prototype. Not a medical device.")
    app.state.service = state
    prefix = f"/api/{API_VERSION}"

    # ----------------------------------------------------------------- errors
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, error: ApiError):
        return _error_response(error)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, error: RequestValidationError):
        errors = [{"field": ".".join(str(p) for p in item["loc"]), "message": item["msg"]} for item in error.errors()]
        return _error_response(ApiError("INVALID_INPUT", "REQUEST_INVALID", "Request validation failed",
                                        {"errors": errors}))

    @app.exception_handler(RecordValidationError)
    async def _record(_: Request, error: RecordValidationError):
        return _error_response(ApiError("INVALID_INPUT", "RECORD_INVALID", str(error), error.to_dict()))

    @app.exception_handler(StorageError)
    async def _storage(_: Request, error: StorageError):
        if isinstance(error, NotFoundError):
            return _error_response(ApiError("NOT_FOUND", error.code, error.message))
        if error.code in ("INTEGRITY_VIOLATION", "MODEL_VERSION_CONFLICT"):
            return _error_response(ApiError("CONFLICT", error.code, error.message))
        return _error_response(ApiError("INFRASTRUCTURE_FAILURE", error.code, error.message))

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, error: Exception):
        log.exception("Unhandled error")
        return _error_response(ApiError("INFRASTRUCTURE_FAILURE", "INTERNAL_ERROR",
                                        f"Unexpected server error: {type(error).__name__}"))

    # ----------------------------------------------------------------- health
    @app.get("/health/live", response_model=LiveResponse)
    def live():
        return LiveResponse(service_version=SERVICE_VERSION)

    @app.get("/health/ready", response_model=ReadinessResponse,
             responses={503: {"model": ReadinessResponse}})
    def ready():
        try:
            database_ok, schema = state.db.ping(), state.db.schema_version()
        except Exception:  # noqa: BLE001 - readiness must never raise
            database_ok, schema = False, None
        model_ok = state.pipeline is not None
        body = ReadinessResponse(
            status="READY" if model_ok and database_ok else "NOT_READY",
            model="READY" if model_ok else "NOT_READY", database="READY" if database_ok else "NOT_READY",
            model_version=state.engine.config.model_version if model_ok else None, schema_version=schema,
            detail=None if model_ok else {"model_error": state.model_error},
        )
        return JSONResponse(body.model_dump(mode="json"), status_code=200 if body.status == "READY" else 503)

    # ----------------------------------------------------------------- model
    @app.get(f"{prefix}/model", response_model=ModelInfoResponse)
    def model_info():
        pipeline = state.require_pipeline()
        return ModelInfoResponse(model=pipeline.engine.describe(), quality_config=state.gate.config.reference(),
                                 measurement_config=state.measurement_config.reference(), limitations=LIMITATIONS)

    # ----------------------------------------------------------------- cases
    @app.post(f"{prefix}/cases", response_model=CaseResponse, status_code=201)
    def create_case(body: CaseCreate):
        case = state.db.add_case(CaseRecord.create(**body.model_dump()))
        return CaseResponse(case=case.to_dict(), examinations=[])

    @app.get(f"{prefix}/cases", response_model=CaseListResponse)
    def list_cases():
        return CaseListResponse(cases=[case.to_dict() for case in state.db.list_cases()])

    @app.get(f"{prefix}/cases/{{case_id}}", response_model=CaseResponse)
    def get_case(case_id: str):
        case = state.db.get_case(case_id)
        return CaseResponse(case=case.to_dict(),
                            examinations=[e.to_dict() for e in state.db.list_examinations(case_id)])

    @app.delete(f"{prefix}/cases/{{case_id}}", response_model=DeleteResponse)
    def delete_case(case_id: str):
        return DeleteResponse(deleted={"case_id": case_id, **state.db.delete_case(case_id, state.blobs)})

    @app.post(f"{prefix}/cases/{{case_id}}/examinations", response_model=ExaminationResponse, status_code=201)
    def create_examination(case_id: str, body: ExaminationCreate):
        state.db.get_case(case_id)
        examination = state.db.add_examination(ExaminationRecord.create(case_id=case_id, **body.model_dump()))
        return ExaminationResponse(examination=examination.to_dict(), analyses=[])

    @app.get(f"{prefix}/examinations/{{examination_id}}", response_model=ExaminationResponse)
    def get_examination(examination_id: str):
        examination = state.db.get_examination(examination_id)
        analyses = [_analysis_response(a, state.db.get_image(a.image_id).to_dict()).model_dump(mode="json")
                    for a in state.db.list_analyses(examination_id)]
        return ExaminationResponse(examination=examination.to_dict(), analyses=analyses)

    # ----------------------------------------------------------------- analysis
    @app.post(f"{prefix}/analyses", response_model=AnalysisResponse, status_code=201,
              responses={code: {"model": ErrorResponse} for code in (400, 404, 413, 422, 500, 503)})
    def analyze(
        file: UploadFile = File(...),
        examination_id: Optional[str] = Form(None),
        pixels_per_mm: Optional[float] = Form(None),
        calibration_method: Optional[str] = Form(None),
        calibration_source: Optional[str] = Form(None),
        threshold: Optional[float] = Form(None),
    ):
        pipeline = state.require_pipeline()
        data = file.file.read(settings.max_upload_bytes + 1)
        if len(data) > settings.max_upload_bytes:
            raise ApiError("INVALID_INPUT", "INPUT_TOO_LARGE",
                           f"Upload exceeds {settings.max_upload_bytes} bytes", status=413)
        if examination_id:
            state.db.get_examination(examination_id)
        calibration = None
        if pixels_per_mm is not None:
            try:
                calibration = Calibration(pixels_per_mm, calibration_method or "USER_ENTERED", calibration_source or "")
            except MeasurementError as error:
                raise ApiError("INVALID_INPUT", error.code, error.message) from error
        elif calibration_method or calibration_source:
            raise ApiError("INVALID_INPUT", "CALIBRATION_INVALID", "calibration_method needs pixels_per_mm")
        try:
            decoded = pipeline.engine.decode(data)
        except InputTooLargeError as error:
            raise ApiError("INVALID_INPUT", error.code, error.message, error.details, status=413) from error
        except InputError as error:
            raise ApiError("INVALID_INPUT", error.code, error.message, error.details) from error

        request_id = new_id("req")
        failure: Optional[InferenceError] = None
        try:
            with state.lock:
                outcome = pipeline.analyze(decoded, calibration=calibration, threshold=threshold, request_id=request_id)
        except InputError as error:  # e.g. invalid threshold
            raise ApiError("INVALID_INPUT", error.code, error.message, error.details) from error
        except InferenceError as error:
            failure, outcome = error, None

        written: List[str] = []
        image_key, _ = state.blobs.put(data, FORMAT_SUFFIX.get(decoded.source_format, ""))
        written.append(image_key)
        if outcome is None:
            image = ImageRecord.create(examination_id=examination_id, sha256=decoded.sha256,
                                       original_filename=file.filename, format=decoded.source_format,
                                       width=decoded.width, height=decoded.height, storage_key=image_key)
            record = AnalysisRecord.create(image_id=image.image_id, examination_id=examination_id, status="FAILED",
                                           quality=state.gate.evaluate(decoded).to_dict(), error=failure.to_dict(),
                                           provenance={"request_id": request_id,
                                                       "model": {"model_version": pipeline.engine.config.model_version}})
            artifacts: List[Dict[str, str]] = []
        else:
            image = image_record_from_outcome(outcome, examination_id, file.filename, image_key)
            record = analysis_record_from_outcome(outcome, image)
            artifacts = []
            if outcome.inference is not None:
                for kind, payload in (("MASK", mask_png(outcome.inference.binary_mask)),
                                      ("PROBABILITY", probability_png(outcome.inference.probability_mask))):
                    key, digest = state.blobs.put(payload, ".png")
                    written.append(key)
                    artifacts.append({"kind": kind, "storage_key": key, "sha256": digest, "media_type": "image/png"})
        try:
            state.db.save_analysis(image, record, artifacts)
        except StorageError:
            for key in written:
                try:
                    if not state.db._blob_referenced(key):
                        state.blobs.delete(key)
                except Exception:  # noqa: BLE001 - best-effort cleanup
                    pass
            raise

        response = _analysis_response(record, image.to_dict())
        if record.status == "FAILED":
            raise ApiError("MODEL_FAILURE", failure.code, failure.message, failure.details, analysis=response)
        if record.status == QUALITY_REJECTED:
            raise ApiError("QUALITY_REJECTED", "QUALITY_REJECTED",
                           "Image rejected by the quality gate: " + ", ".join(record.quality["reason_codes"]),
                           {"reason_codes": record.quality["reason_codes"]}, analysis=response)
        return response

    @app.get(f"{prefix}/analyses/{{analysis_id}}", response_model=AnalysisResponse)
    def get_analysis(analysis_id: str):
        record = state.db.get_analysis(analysis_id)
        return _analysis_response(record, state.db.get_image(record.image_id).to_dict())

    @app.get(f"{prefix}/analyses/{{analysis_id}}/image")
    def get_image(analysis_id: str):
        image = state.db.get_image(state.db.get_analysis(analysis_id).image_id)
        return Response(state.blobs.get(image.storage_key), media_type=MEDIA_TYPE.get(image.format))

    @app.get(f"{prefix}/analyses/{{analysis_id}}/mask.png")
    def get_mask(analysis_id: str):
        return Response(state.blobs.get(state.db.get_artifact(analysis_id, "MASK")["storage_key"]),
                        media_type="image/png")

    @app.get(f"{prefix}/analyses/{{analysis_id}}/probability.png")
    def get_probability(analysis_id: str):
        return Response(state.blobs.get(state.db.get_artifact(analysis_id, "PROBABILITY")["storage_key"]),
                        media_type="image/png")

    @app.get(f"{prefix}/analyses/{{analysis_id}}/overlay.png")
    def get_overlay(analysis_id: str, max_side: int = Query(1024, ge=64, le=8192)):
        record = state.db.get_analysis(analysis_id)
        image = state.db.get_image(record.image_id)
        mask = decode_mask_png(state.blobs.get(state.db.get_artifact(analysis_id, "MASK")["storage_key"]))
        decoded = decode_image(state.blobs.get(image.storage_key))
        return Response(overlay_png(decoded.image, mask, max_side), media_type="image/png")

    # ----------------------------------------------------------------- longitudinal
    @app.get(f"{prefix}/cases/{{case_id}}/trend", response_model=TrendResponse)
    def trend(case_id: str):
        case = state.db.get_case(case_id)
        pairs = state.db.latest_analysis_per_examination(case_id)
        result = build_trend([MeasurementPoint(case, e, a) for e, a in pairs], CompatibilityPolicy()).to_dict()
        analysed = {e.examination_id for e, _ in pairs}
        for examination in state.db.list_examinations(case_id):
            if examination.examination_id not in analysed:
                result["excluded"].append({"examination_id": examination.examination_id, "analysis_id": None,
                                           "reason_codes": ["NO_ANALYSIS"]})
        return TrendResponse(trend=result)

    @app.get(f"{prefix}/compare", response_model=ComparisonResponse)
    def compare_analyses(analysis_a: str, analysis_b: str):
        a, b = state.db.get_analysis(analysis_a), state.db.get_analysis(analysis_b)
        return ComparisonResponse(comparison=compare(_point(state, a), _point(state, b),
                                                     CompatibilityPolicy()).to_dict())

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
