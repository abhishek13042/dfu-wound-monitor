"""P09-S03 mask corrections.

A user can redraw the model's outline.  Each correction is stored as a new
numbered version beside the analysis, which is never changed
(REQ-P09-S03-002), and is measured on the server by the same engine as the
original (REQ-P09-S03-003).  Trends say which values came from a corrected
outline (REQ-P09-S03-004).  A correction is shared for research only when its
author opts in, and corrections are never training labels without review
(REQ-P09-S03-005).
"""

from __future__ import annotations

import io
from collections.abc import Callable
from typing import Any

import numpy as np
from fastapi import APIRouter, Depends, File, Form, UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict

from src.api.errors import ApiError
from src.api.rendering import mask_png
from src.api.schemas import API_V2
from src.api.service import ServiceState
from src.api.uploads import DOWNLOAD_URL_SECONDS, SignedUrlResponse, _timestamp
from src.inference.pipeline import COMPLETED
from src.longitudinal.records import AnalysisRecord
from src.measurement.engine import Calibration, measure
from src.storage.database import StorageError
from src.storage.repository import Repository

MASK_SOURCE_MODEL = "MODEL"
MASK_SOURCE_CORRECTED = "CORRECTED"
CORRECTED_WARNING = {"code": "CORRECTED_MASK",
                     "message": "Measured from an outline corrected by hand, not the model's own outline"}


class CorrectionOut(BaseModel):
    correction_id: str
    analysis_id: str
    version: int
    author: str
    created_at: str
    sha256: str
    measurement: dict[str, Any]
    research_opt_in: bool
    links: dict[str, str]


class CorrectionList(BaseModel):
    api_version: str = API_V2
    analysis_id: str
    corrections: list[CorrectionOut]


class ResearchUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    opt_in: bool


def correction_out(row: dict[str, Any]) -> CorrectionOut:
    base = f"/api/{API_V2}/corrections/{row['correction_id']}"
    return CorrectionOut(**{key: value for key, value in row.items() if key != "storage_key"},
                         links={"self": base, "mask": f"{base}/mask"})


def read_mask(data: bytes, width: int, height: int) -> np.ndarray:
    """A PNG the size of the image, with every value 0 or 255; anything else is ``INVALID_INPUT``.

    Grey, grey with alpha, RGB and RGBA are read alike when every pixel is black or white and opaque.
    """

    try:
        image = Image.open(io.BytesIO(data))
        image_format, size = image.format, image.size
    except (UnidentifiedImageError, OSError) as error:
        raise ApiError("INVALID_INPUT", "MASK_NOT_PNG", "The corrected mask must be a PNG") from error
    if image_format != "PNG":
        raise ApiError("INVALID_INPUT", "MASK_NOT_PNG", "The corrected mask must be a PNG")
    if size != (width, height):  # checked before decoding, so a huge header costs nothing
        raise ApiError("INVALID_INPUT", "MASK_SIZE_MISMATCH", "The mask must be the same size as the image",
                       {"expected": [width, height], "received": list(size)})
    try:
        pixels = np.asarray(image.convert("L") if image.mode in ("1", "P") else image)
    except OSError as error:
        raise ApiError("INVALID_INPUT", "MASK_NOT_PNG", "The corrected mask could not be decoded") from error
    if pixels.ndim == 3:
        # A browser canvas only writes RGBA, so grey drawn opaquely is accepted as the same mask.
        colour, alpha = (pixels[..., :1], pixels[..., 1]) if image.mode == "LA" else (pixels[..., :3], None)
        if image.mode == "RGBA":
            alpha = pixels[..., 3]
        if (colour != colour[..., :1]).any():
            raise ApiError("INVALID_INPUT", "MASK_NOT_GRAYSCALE", "The mask must be black and white",
                           {"mode": image.mode})
        if alpha is not None and (alpha != 255).any():
            raise ApiError("INVALID_INPUT", "MASK_VALUES", "The mask must be fully opaque")
        pixels = colour[..., 0]
    if pixels.ndim != 2:
        raise ApiError("INVALID_INPUT", "MASK_NOT_GRAYSCALE", "The mask must be a single-channel PNG",
                       {"mode": image.mode})
    if not np.isin(pixels, (0, 255)).all():
        raise ApiError("INVALID_INPUT", "MASK_VALUES", "Mask values must be 0 or 255")
    return pixels == 255


def measure_correction(record: AnalysisRecord, mask: np.ndarray) -> dict[str, Any]:
    """The same engine and calibration as the original; only the outline differs."""

    calibration = Calibration(**record.calibration) if record.calibration else None
    result = measure(mask.astype(np.uint8), calibration=calibration,
                     provenance={"mask_source": MASK_SOURCE_CORRECTED, "analysis_id": record.analysis_id,
                                 "model_version": record.model_version})
    # A hand-drawn outline has no model score, so the missing-probability note would mislead.
    result.warnings = [w for w in result.warnings if w["code"] != "CONFIDENCE_NOT_ASSESSED"] + [CORRECTED_WARNING]
    return result.to_dict()


def corrected_record(record: AnalysisRecord, correction: dict[str, Any]) -> AnalysisRecord:
    """A copy of the analysis carrying the corrected measurement, for trends.  The stored record is untouched."""

    measurement = {key: value for key, value in correction["measurement"].items() if key != "provenance"}
    provenance = {**record.provenance, "mask_source": {"kind": MASK_SOURCE_CORRECTED,
                                                       "correction_id": correction["correction_id"],
                                                       "version": correction["version"]}}
    return record.model_copy(update={"measurement": measurement, "provenance": provenance})


def router(state: ServiceState, current_repository: Callable[..., Repository]) -> APIRouter:
    routes = APIRouter(prefix=f"/api/{API_V2}")
    limit = state.settings.max_upload_bytes

    @routes.post("/analyses/{analysis_id}/corrections", response_model=CorrectionOut, status_code=201)
    def create(analysis_id: str, file: UploadFile = File(...), research_opt_in: bool = Form(False),
               db: Repository = Depends(current_repository)):
        record = db.get_analysis(analysis_id)
        if record.status != COMPLETED:
            raise ApiError("CONFLICT", "ANALYSIS_NOT_COMPLETED", "Only a completed analysis has an outline to correct")
        data = file.file.read(limit + 1)
        if len(data) > limit:
            raise ApiError("INVALID_INPUT", "MASK_TOO_LARGE", "The corrected mask is too large",
                           {"max_bytes": limit}, status=413)
        image = db.get_image(record.image_id)
        mask = read_mask(data, image.width, image.height)
        measurement = measure_correction(record, mask)
        key, digest = state.blobs.put(mask_png(mask), ".png")  # stored canonical: the same mask, the same bytes
        try:
            row = db.add_correction(analysis_id, key, digest, measurement, research_opt_in)
        except StorageError:
            if not db.blob_referenced(key):
                state.blobs.delete(key)
            raise
        return correction_out(row)

    @routes.get("/analyses/{analysis_id}/corrections", response_model=CorrectionList)
    def list_all(analysis_id: str, db: Repository = Depends(current_repository)):
        return CorrectionList(analysis_id=analysis_id,
                              corrections=[correction_out(row) for row in db.list_corrections(analysis_id)])

    @routes.get("/corrections/{correction_id}/mask", response_model=SignedUrlResponse)
    def mask_url(correction_id: str, db: Repository = Depends(current_repository)):
        row = db.get_correction(correction_id)  # the owner check comes before any URL exists
        return SignedUrlResponse(url=state.blobs.presign(row["storage_key"], "GET", DOWNLOAD_URL_SECONDS),
                                 expires_at=_timestamp(DOWNLOAD_URL_SECONDS))

    @routes.put("/corrections/{correction_id}/research", response_model=CorrectionOut)
    def set_research(correction_id: str, body: ResearchUpdate, db: Repository = Depends(current_repository)):
        return correction_out(db.set_correction_research(correction_id, body.opt_in))

    return routes
