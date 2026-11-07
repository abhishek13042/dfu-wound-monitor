"""REQ-P09-S01-001/002: scale from a printed ArUco marker, or a reason why not.

The marker never guesses: a missing, cut-off, too-small, tilted or duplicated marker returns a reason code and no
calibration, so the caller keeps the user's scale or falls back to pixels.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.measurement.engine import Calibration, MeasurementError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MARKER_CONFIG = PROJECT_ROOT / "configs" / "measurement" / "marker_v1.json"
ARUCO_MARKER = "ARUCO_MARKER"

FOUND = "MARKER_FOUND"
NOT_FOUND = "MARKER_NOT_FOUND"
WRONG_ID = "MARKER_WRONG_ID"
PARTIAL = "MARKER_PARTIAL"
TOO_SMALL = "MARKER_TOO_SMALL"
TILTED = "MARKER_TILTED"
AMBIGUOUS = "MARKER_AMBIGUOUS"

REASONS = {
    WRONG_ID: "A marker was found, but not the agreed one",
    PARTIAL: "The marker touches the edge of the photo, so its size cannot be trusted",
    TOO_SMALL: "The marker is too small in the photo for a reliable scale",
    TILTED: "The marker is seen at too steep an angle for a reliable scale",
    AMBIGUOUS: "More than one copy of the marker is in the photo",
}


@dataclass(frozen=True)
class MarkerConfig:
    path: str
    version: str
    sha256: str
    enabled: bool
    dictionary: str
    marker_id: int
    side_mm: float
    min_side_px: float
    max_side_ratio: float
    max_corner_deviation_deg: float
    border_margin_px: float
    conflict_tolerance_pct: float

    @classmethod
    def load(cls, path: str | Path = DEFAULT_MARKER_CONFIG) -> MarkerConfig:
        path = Path(path)
        data = path.read_bytes()
        raw = json.loads(data)
        if not hasattr(cv2.aruco, raw["dictionary"]):
            raise MeasurementError("CONFIG_INVALID", f"Unknown ArUco dictionary {raw['dictionary']!r}")
        config = cls(str(path), str(raw["marker_config_version"]), hashlib.sha256(data).hexdigest(),
                     bool(raw.get("enabled", True)), str(raw["dictionary"]), int(raw["marker_id"]),
                     float(raw["side_mm"]), float(raw["min_side_px"]), float(raw["max_side_ratio"]),
                     float(raw["max_corner_deviation_deg"]), float(raw["border_margin_px"]),
                     float(raw["conflict_tolerance_pct"]))
        if config.side_mm <= 0 or config.max_side_ratio < 1 or config.conflict_tolerance_pct <= 0:
            raise MeasurementError("CONFIG_INVALID", "side_mm, max_side_ratio or conflict_tolerance_pct is out of range")
        return config

    def reference(self) -> dict[str, Any]:
        return {"path": self.path, "version": self.version, "sha256": self.sha256}


@dataclass(frozen=True)
class MarkerReading:
    status: str                                 # FOUND or one of the reason codes
    calibration: Calibration | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def found(self) -> bool:
        return self.status == FOUND

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, **self.details}


def _corner_deviation(quad: np.ndarray) -> float:
    worst = 0.0
    for index in range(4):
        a, b, c = quad[index - 1], quad[index], quad[(index + 1) % 4]
        u, v = a - b, c - b
        cosine = float(np.dot(u, v) / (np.linalg.norm(u) * np.linalg.norm(v)))
        worst = max(worst, abs(math.degrees(math.acos(max(-1.0, min(1.0, cosine)))) - 90.0))
    return worst


def detect_marker(rgb: np.ndarray, config: MarkerConfig | None = None) -> MarkerReading:
    """Find the agreed marker in an RGB uint8 image and turn it into a scale, or say why not."""
    config = config or MarkerConfig.load()
    gray = cv2.cvtColor(np.ascontiguousarray(rgb), cv2.COLOR_RGB2GRAY) if rgb.ndim == 3 else rgb
    dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, config.dictionary))
    parameters = cv2.aruco.DetectorParameters()
    parameters.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    corners, ids, _ = cv2.aruco.ArucoDetector(dictionary, parameters).detectMarkers(gray)
    base = {"dictionary": config.dictionary, "marker_id": config.marker_id, "config": config.reference()}
    if ids is None or len(ids) == 0:
        return MarkerReading(NOT_FOUND, details=base)
    seen = [int(value) for value in ids.ravel()]
    matches = [np.asarray(corners[i], dtype=np.float64).reshape(4, 2) for i, value in enumerate(seen)
               if value == config.marker_id]
    if not matches:
        return MarkerReading(WRONG_ID, details={**base, "ids_seen": sorted(set(seen))})
    if len(matches) > 1:
        return MarkerReading(AMBIGUOUS, details={**base, "copies": len(matches)})
    quad = matches[0]
    sides = [float(np.linalg.norm(quad[(i + 1) % 4] - quad[i])) for i in range(4)]
    mean_side = sum(sides) / 4
    ratio = max(sides) / min(sides)
    deviation = _corner_deviation(quad)
    height, width = gray.shape[:2]
    margin = config.border_margin_px
    measured = {**base, "corners_px": quad.round(2).tolist(), "side_px": round(mean_side, 3),
                "side_ratio": round(ratio, 4), "corner_deviation_deg": round(deviation, 2)}
    if (quad[:, 0].min() < margin or quad[:, 1].min() < margin
            or quad[:, 0].max() > width - 1 - margin or quad[:, 1].max() > height - 1 - margin):
        return MarkerReading(PARTIAL, details=measured)
    if mean_side < config.min_side_px:
        return MarkerReading(TOO_SMALL, details=measured)
    if ratio > config.max_side_ratio or deviation > config.max_corner_deviation_deg:
        return MarkerReading(TILTED, details=measured)
    # Uncertainty: half the spread of the four sides plus one pixel of corner error, as a share of the side.
    uncertainty = min(99.0, 100.0 * ((max(sides) - min(sides)) / 2 + 1.0) / mean_side)
    calibration = Calibration(mean_side / config.side_mm, ARUCO_MARKER,
                              f"aruco {config.dictionary} id {config.marker_id}", round(uncertainty, 3))
    return MarkerReading(FOUND, calibration, measured)
