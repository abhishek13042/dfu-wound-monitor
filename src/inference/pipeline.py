"""Analysis pipeline: decode once -> quality gate -> segmentation -> measurement.

A rejected image never reaches the model (REQ-P03-S02-003).  Undecodable or
disallowed input raises a typed ``InputError`` so callers can tell invalid
input apart from a quality rejection and from a model failure.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from src.inference.engine import InferenceEngine, InferenceRequest, InferenceResult
from src.measurement.engine import Calibration, MeasurementConfig, MeasurementResult, measure
from src.preprocessing.decode import DecodedImage, ImageSource
from src.quality.gate import QualityGate, QualityResult

COMPLETED, QUALITY_REJECTED = "COMPLETED", "QUALITY_REJECTED"


@dataclass
class AnalysisOutcome:
    request_id: str
    status: str                                   # COMPLETED | QUALITY_REJECTED
    decoded: DecodedImage
    quality: QualityResult
    inference: InferenceResult | None = None
    measurement: MeasurementResult | None = None
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "input": {"sha256": self.decoded.sha256, "format": self.decoded.source_format,
                      "width": self.decoded.width, "height": self.decoded.height},
            "quality": self.quality.to_dict(),
            "inference": self.inference.summary() if self.inference else None,
            "measurement": self.measurement.to_dict() if self.measurement else None,
            "warnings": self.warnings,
        }


class AnalysisPipeline:
    def __init__(self, engine: InferenceEngine, gate: QualityGate | None = None,
                 measurement_config: MeasurementConfig | None = None) -> None:
        self.engine = engine
        self.gate = gate or QualityGate()
        self.measurement_config = measurement_config or MeasurementConfig.load()

    def analyze(self, image: ImageSource | DecodedImage, *, calibration: Calibration | None = None,
                threshold: float | None = None, request_id: str | None = None) -> AnalysisOutcome:
        request_id = request_id or uuid.uuid4().hex
        decoded = self.engine.decode(image)            # raises InputError subclasses
        quality = self.gate.evaluate(decoded)
        if not quality.accepted:
            return AnalysisOutcome(request_id, QUALITY_REJECTED, decoded, quality)
        inference = self.engine.predict(InferenceRequest(decoded, threshold=threshold, request_id=request_id))
        measurement = measure(inference.binary_mask, calibration=calibration,
                              probability_mask=inference.probability_mask, provenance=inference.provenance,
                              config=self.measurement_config)
        warnings = list(inference.warnings) + [w for w in measurement.warnings
                                               if w["code"] not in {x["code"] for x in inference.warnings}]
        return AnalysisOutcome(request_id, COMPLETED, decoded, quality, inference, measurement, warnings)
