"""Analyse an image and persist the result.

This is the one path from image bytes to stored records.  The v1 upload route,
the v2 route and the worker all call it, so they cannot drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.api.errors import ApiError
from src.api.rendering import mask_png, probability_png
from src.api.schemas import API_VERSION, AnalysisResponse
from src.api.service import ServiceState
from src.inference.errors import InferenceError, InputError, InputTooLargeError
from src.inference.pipeline import COMPLETED, AnalysisPipeline
from src.longitudinal.records import (
    AnalysisRecord,
    ImageRecord,
    analysis_record_from_outcome,
    image_record_from_outcome,
    new_id,
)
from src.measurement.engine import LIMITATION, Calibration, MeasurementError
from src.preprocessing.decode import DecodedImage
from src.storage.database import StorageError
from src.storage.repository import Repository

FORMAT_SUFFIX = {"PNG": ".png", "JPEG": ".jpg", "BMP": ".bmp", "TIFF": ".tif", "WEBP": ".webp"}
MEDIA_TYPE = {"PNG": "image/png", "JPEG": "image/jpeg", "BMP": "image/bmp", "TIFF": "image/tiff", "WEBP": "image/webp"}


@dataclass
class StoredAnalysis:
    image: ImageRecord
    record: AnalysisRecord
    failure: InferenceError | None = None


def parse_calibration(pixels_per_mm: float | None, method: str | None, source: str | None) -> Calibration | None:
    if pixels_per_mm is None:
        if method or source:
            raise ApiError("INVALID_INPUT", "CALIBRATION_INVALID", "calibration_method needs pixels_per_mm")
        return None
    try:
        return Calibration(pixels_per_mm, method or "USER_ENTERED", source or "")
    except MeasurementError as error:
        raise ApiError("INVALID_INPUT", error.code, error.message) from error


def decode_input(pipeline: AnalysisPipeline, data: bytes) -> DecodedImage:
    try:
        return pipeline.engine.decode(data)
    except InputTooLargeError as error:
        raise ApiError("INVALID_INPUT", error.code, error.message, error.details, status=413) from error
    except InputError as error:
        raise ApiError("INVALID_INPUT", error.code, error.message, error.details) from error


def analyse_and_store(state: ServiceState, data: bytes, *, filename: str | None, examination_id: str | None,
                      calibration: Calibration | None, threshold: float | None,
                      analysis_id: str | None = None, db: Repository | None = None) -> StoredAnalysis:
    db = db or state.db
    pipeline = state.require_pipeline()
    decoded = decode_input(pipeline, data)
    request_id = new_id("req")
    failure: InferenceError | None = None
    try:
        with state.lock:
            outcome = pipeline.analyze(decoded, calibration=calibration, threshold=threshold, request_id=request_id)
    except InputError as error:  # e.g. invalid threshold
        raise ApiError("INVALID_INPUT", error.code, error.message, error.details) from error
    except InferenceError as error:
        failure, outcome = error, None

    written: list[str] = []
    image_key, _ = state.blobs.put(data, FORMAT_SUFFIX.get(decoded.source_format, ""))
    written.append(image_key)
    identifiers = {"analysis_id": analysis_id} if analysis_id else {}
    if outcome is None:
        assert failure is not None  # analyze() returned nothing only by raising
        image = ImageRecord.create(examination_id=examination_id, sha256=decoded.sha256, original_filename=filename,
                                   format=decoded.source_format, width=decoded.width, height=decoded.height,
                                   storage_key=image_key)
        record = AnalysisRecord.create(image_id=image.image_id, examination_id=examination_id, status="FAILED",
                                       quality=state.gate.evaluate(decoded).to_dict(), error=failure.to_dict(),
                                       provenance={"request_id": request_id,
                                                   "model": {"model_version": pipeline.engine.config.model_version}},
                                       **identifiers)
        artifacts: list[dict[str, str]] = []
    else:
        image = image_record_from_outcome(outcome, examination_id, filename, image_key)
        record = analysis_record_from_outcome(outcome, image, analysis_id)
        artifacts = []
        if outcome.inference is not None:
            for kind, payload in (("MASK", mask_png(outcome.inference.binary_mask)),
                                  ("PROBABILITY", probability_png(outcome.inference.probability_mask))):
                key, digest = state.blobs.put(payload, ".png")
                written.append(key)
                artifacts.append({"kind": kind, "storage_key": key, "sha256": digest, "media_type": "image/png"})
    try:
        db.save_analysis(image, record, artifacts)
    except StorageError:
        for key in written:
            try:
                if not db.blob_referenced(key):
                    state.blobs.delete(key)
            except Exception:  # noqa: BLE001 - best-effort cleanup
                pass
        raise
    return StoredAnalysis(image, record, failure)


def analysis_response(record: AnalysisRecord, image: dict, version: str = API_VERSION) -> AnalysisResponse:
    base = f"/api/{version}/analyses/{record.analysis_id}"
    if version == API_VERSION:
        links = {"self": base, "image": f"{base}/image"}
        if record.status == COMPLETED:
            links.update(mask=f"{base}/mask.png", overlay=f"{base}/overlay.png", probability=f"{base}/probability.png")
    else:
        links = {"self": base, "image": f"{base}/artifacts/image"}
        if record.status == COMPLETED:
            links.update(mask=f"{base}/artifacts/mask", probability=f"{base}/artifacts/probability")
    return AnalysisResponse(api_version=version, analysis_id=record.analysis_id, status=record.status, image=image,
                            quality=record.quality, model_version=record.model_version,
                            measurement=record.measurement, inference=record.inference_summary,
                            warnings=record.warnings, provenance=record.provenance, links=links,
                            limitation=LIMITATION)
