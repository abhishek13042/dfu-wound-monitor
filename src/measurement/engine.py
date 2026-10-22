"""P03-S03 wound measurement engine.

Derives geometric measurements from a binary wound mask.  Pixel measurements
are always produced; physical (mm) measurements are produced **only** when a
valid ``Calibration`` is supplied (REQ-P03-S03-002/003).

Definitions (all on the native-resolution mask, 8-connected components):

* ``area_px``             number of foreground pixels.
* ``perimeter_px``        boundary length estimated from the 4-connected
                          border pixels with the weighted neighbourhood scheme
                          of Benkrid & Crookes (also used by scikit-image).
                          Hole boundaries are included.  Documented
                          tolerance: within 5% for digital discs of radius
                          >= 10 px (see tests).  One-pixel-wide structures
                          are under-measured (a line counts ~once, not twice).
* ``bbox``                axis-aligned ``[x_min, y_min, x_max, y_max]``,
                          inclusive.
* ``max_feret_px``        longest distance between two points of the convex
                          hull of the pixel squares ("length").
* ``min_feret_px``        smallest caliper width of that hull ("width").
* ``equivalent_diameter_px``  diameter of the disc with the same area.
* ``circularity``         ``4*pi*area / perimeter**2``, capped at 1.0.
* ``solidity``            ``area / convex hull area``.
* ``extent``              ``area / bbox area``.

Physical values divide lengths by ``pixels_per_mm`` and areas by its square.
They are 2-D projected measurements in the image plane.  Foot curvature,
camera tilt and lens distortion are not corrected.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
from scipy import ndimage
from scipy.spatial import ConvexHull, QhullError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MEASUREMENT_CONFIG = PROJECT_ROOT / "configs" / "measurement" / "measurement_v1.json"
ENGINE_VERSION = "p03-s03-1.0"
PIXEL_BASED, PHYSICALLY_CALIBRATED = "PIXEL_BASED", "PHYSICALLY_CALIBRATED"
CALIBRATION_METHODS = ("REFERENCE_MARKER", "USER_ENTERED")
LIMITATION = ("Image-derived 2-D projected geometry. Foot curvature, camera angle and lens distortion are not "
              "corrected. Not a clinical measurement.")

# Perimeter weights for the 4-connected border convolution (values 0..49).
_PERIMETER_WEIGHTS = np.zeros(50, dtype=np.float64)
_PERIMETER_WEIGHTS[[5, 7, 15, 17, 25, 27]] = 1.0
_PERIMETER_WEIGHTS[[21, 33]] = math.sqrt(2.0)
_PERIMETER_WEIGHTS[[13, 23]] = (1.0 + math.sqrt(2.0)) / 2.0
_PERIMETER_KERNEL = np.array([[10, 2, 10], [2, 1, 2], [10, 2, 10]], dtype=np.int64)
_CROSS = ndimage.generate_binary_structure(2, 1)


class MeasurementError(Exception):
    category = "INPUT"

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message

    def to_dict(self) -> Dict[str, Any]:
        return {"category": self.category, "code": self.code, "message": self.message}


@dataclass(frozen=True)
class Calibration:
    """Scale metadata.  ``pixels_per_mm`` must be finite and positive."""

    pixels_per_mm: float
    method: str
    source: str = ""
    uncertainty_pct: Optional[float] = None

    def __post_init__(self) -> None:
        value = self.pixels_per_mm
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise MeasurementError("CALIBRATION_INVALID", f"pixels_per_mm must be a finite positive number, got {value!r}")
        if self.method not in CALIBRATION_METHODS:
            raise MeasurementError("CALIBRATION_INVALID", f"method must be one of {CALIBRATION_METHODS}, got {self.method!r}")
        if self.uncertainty_pct is not None and not (0 <= self.uncertainty_pct < 100):
            raise MeasurementError("CALIBRATION_INVALID", "uncertainty_pct must be in [0, 100)")


@dataclass(frozen=True)
class MeasurementConfig:
    path: str
    version: str
    sha256: str
    low_confidence_mean_probability: float
    min_reliable_area_px: int
    max_reported_components: int

    @classmethod
    def load(cls, path: Union[str, Path] = DEFAULT_MEASUREMENT_CONFIG) -> "MeasurementConfig":
        path = Path(path)
        data = path.read_bytes()
        raw = json.loads(data)
        if int(raw.get("connectivity", 8)) != 8:
            raise MeasurementError("CONFIG_INVALID", "Only 8-connectivity is supported (matches inference)")
        return cls(str(path), str(raw["measurement_config_version"]), hashlib.sha256(data).hexdigest(),
                   float(raw["low_confidence_mean_probability"]), int(raw["min_reliable_area_px"]),
                   int(raw.get("max_reported_components", 20)))

    def reference(self) -> Dict[str, Any]:
        return {"path": self.path, "version": self.version, "sha256": self.sha256}


@dataclass
class MeasurementResult:
    measurement_basis: str                  # PIXEL_BASED | PHYSICALLY_CALIBRATED
    status: str                             # MEASURED | EMPTY
    pixel: Dict[str, Any]
    physical: Optional[Dict[str, Any]]      # None unless calibrated
    components: List[Dict[str, Any]]
    confidence: Optional[Dict[str, Any]]
    calibration: Optional[Dict[str, Any]]
    warnings: List[Dict[str, Any]]
    provenance: Dict[str, Any]
    limitation: str = LIMITATION
    units: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MeasurementResult":
        return cls(**data)


def _validate_mask(mask: Any) -> np.ndarray:
    if not isinstance(mask, np.ndarray):
        raise MeasurementError("MASK_MALFORMED", f"mask must be a numpy array, got {type(mask).__name__}")
    if mask.ndim != 2 or 0 in mask.shape:
        raise MeasurementError("MASK_MALFORMED", f"mask must be a non-empty 2-D array, got shape {mask.shape}")
    if mask.dtype == bool:
        return mask.astype(np.uint8)
    if not np.issubdtype(mask.dtype, np.number) or not np.isfinite(mask).all():
        raise MeasurementError("MASK_MALFORMED", "mask must be numeric and finite")
    values = np.unique(mask)
    if not set(values.tolist()) <= {0, 1}:
        raise MeasurementError("MASK_MALFORMED", f"mask must be binary {{0,1}}, found values {values[:6].tolist()}")
    return mask.astype(np.uint8)


def perimeter_px(mask: np.ndarray) -> float:
    if not mask.any():
        return 0.0
    padded = np.pad(mask.astype(np.uint8), 1)
    border = padded - ndimage.binary_erosion(padded, structure=_CROSS, border_value=0).astype(np.uint8)
    codes = ndimage.convolve(border.astype(np.int64), _PERIMETER_KERNEL, mode="constant", cval=0)
    return float(_PERIMETER_WEIGHTS[codes[border.astype(bool)]].sum()) if border.any() else 0.0


def _hull_geometry(mask: np.ndarray) -> Dict[str, float]:
    """Convex hull of the pixel squares: hull area and min/max Feret diameters."""

    border = mask.astype(bool) & ~ndimage.binary_erosion(mask.astype(bool), structure=_CROSS, border_value=0)
    ys, xs = np.nonzero(border)
    corners = np.concatenate([np.stack([xs + dx, ys + dy], axis=1) for dx in (0, 1) for dy in (0, 1)]).astype(float)
    corners = np.unique(corners, axis=0)
    try:
        hull = ConvexHull(corners)
    except QhullError:
        return {"hull_area": float(mask.sum()), "max_feret": 1.0, "min_feret": 1.0}
    vertices = corners[hull.vertices]
    diffs = vertices[:, None, :] - vertices[None, :, :]
    max_feret = float(np.sqrt((diffs ** 2).sum(-1)).max())
    min_feret = math.inf
    for index in range(len(vertices)):
        edge = vertices[(index + 1) % len(vertices)] - vertices[index]
        length = float(np.hypot(*edge))
        if length == 0:
            continue
        normal = np.array([-edge[1], edge[0]]) / length
        projection = vertices @ normal
        min_feret = min(min_feret, float(projection.max() - projection.min()))
    return {"hull_area": float(hull.volume), "max_feret": max_feret, "min_feret": min_feret}


def _region_geometry(mask: np.ndarray) -> Dict[str, Any]:
    area = int(mask.sum())
    ys, xs = np.nonzero(mask)
    x_min, x_max, y_min, y_max = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    perimeter = perimeter_px(mask)
    hull = _hull_geometry(mask)
    bbox_area = (x_max - x_min + 1) * (y_max - y_min + 1)
    return {
        "area_px": area,
        "perimeter_px": round(perimeter, 4),
        "bbox": [x_min, y_min, x_max, y_max],
        "bbox_width_px": x_max - x_min + 1,
        "bbox_height_px": y_max - y_min + 1,
        "centroid_xy": [round(float(xs.mean()), 3), round(float(ys.mean()), 3)],
        "max_feret_px": round(hull["max_feret"], 4),
        "min_feret_px": round(hull["min_feret"], 4),
        "equivalent_diameter_px": round(math.sqrt(4 * area / math.pi), 4),
        "circularity": round(min(1.0, 4 * math.pi * area / perimeter ** 2), 4) if perimeter > 0 else None,
        "solidity": round(min(1.0, area / hull["hull_area"]), 4) if hull["hull_area"] > 0 else None,
        "extent": round(area / bbox_area, 4),
    }


def _to_physical(pixel: Dict[str, Any], ppm: float) -> Dict[str, Any]:
    lengths = ("perimeter_px", "bbox_width_px", "bbox_height_px", "max_feret_px", "min_feret_px",
               "equivalent_diameter_px")
    physical = {"area_mm2": round(pixel["area_px"] / ppm ** 2, 4)}
    for key in lengths:
        physical[key.replace("_px", "_mm")] = round(pixel[key] / ppm, 4)
    return physical


def measure(
    mask: np.ndarray,
    calibration: Optional[Calibration] = None,
    probability_mask: Optional[np.ndarray] = None,
    provenance: Optional[Dict[str, Any]] = None,
    config: Optional[MeasurementConfig] = None,
) -> MeasurementResult:
    config = config or MeasurementConfig.load()
    binary = _validate_mask(mask)
    if probability_mask is not None:
        if not isinstance(probability_mask, np.ndarray) or probability_mask.shape != binary.shape:
            raise MeasurementError("PROBABILITY_MALFORMED", "probability_mask must match the mask shape")
        if not np.isfinite(probability_mask).all() or probability_mask.min() < 0 or probability_mask.max() > 1:
            raise MeasurementError("PROBABILITY_MALFORMED", "probability_mask values must be finite and in [0,1]")
    basis = PHYSICALLY_CALIBRATED if calibration is not None else PIXEL_BASED
    warnings: List[Dict[str, Any]] = []
    full_provenance = {
        **(provenance or {}),
        "measurement": {"engine_version": ENGINE_VERSION, "config": config.reference(),
                        "mask_shape": list(binary.shape), "connectivity": 8},
    }
    units = {"pixel": "px / px^2", "physical": "mm / mm^2" if calibration else "not available (no calibration)"}
    calibration_dict = asdict(calibration) if calibration else None
    if calibration is None:
        warnings.append({"code": "UNCALIBRATED", "message": "No scale metadata: only pixel measurements are reported"})

    if not binary.any():
        warnings.append({"code": "EMPTY_MASK", "message": "Mask contains no foreground; geometry is undefined"})
        empty_pixel = {"area_px": 0, "perimeter_px": 0.0, "component_count": 0}
        empty_physical = {"area_mm2": 0.0, "perimeter_mm": 0.0} if calibration else None
        return MeasurementResult(basis, "EMPTY", empty_pixel, empty_physical, [], None, calibration_dict, warnings,
                                 full_provenance, units=units)

    labels, count = ndimage.label(binary, structure=np.ones((3, 3), dtype=np.uint8))
    areas = np.bincount(labels.ravel())[1:]
    order = np.argsort(-areas, kind="stable")
    components = []
    for rank, index in enumerate(order[: config.max_reported_components]):
        component = _region_geometry((labels == index + 1).astype(np.uint8))
        component["rank"] = rank + 1
        components.append(component)

    pixel = _region_geometry(binary)
    pixel["component_count"] = int(count)
    pixel["largest_component_area_px"] = int(areas.max())
    if count > 1:
        warnings.append({"code": "MULTIPLE_COMPONENTS",
                         "message": f"{count} separate regions; totals sum all of them",
                         "component_count": int(count)})
    if count > config.max_reported_components:
        warnings.append({"code": "COMPONENTS_TRUNCATED",
                         "message": f"Only the {config.max_reported_components} largest components are listed"})
    if binary[0].any() or binary[-1].any() or binary[:, 0].any() or binary[:, -1].any():
        warnings.append({"code": "TOUCHES_IMAGE_BORDER",
                         "message": "Region touches the image edge; the wound may extend beyond the frame"})
    if pixel["area_px"] < config.min_reliable_area_px:
        warnings.append({"code": "SMALL_REGION",
                         "message": f"Area below {config.min_reliable_area_px} px; relative error of the geometry is high"})

    confidence = None
    if probability_mask is not None:
        inside = probability_mask[binary.astype(bool)].astype(np.float64)
        confidence = {
            "mean_probability_in_mask": round(float(inside.mean()), 4),
            "uncertain_fraction": round(float(((inside >= 0.3) & (inside <= 0.7)).mean()), 4),
            "low_confidence_threshold": config.low_confidence_mean_probability,
        }
        if confidence["mean_probability_in_mask"] < config.low_confidence_mean_probability:
            warnings.append({"code": "LOW_CONFIDENCE",
                             "message": "Mean model probability inside the mask is below the configured threshold"})
    else:
        warnings.append({"code": "CONFIDENCE_NOT_ASSESSED", "message": "No probability map supplied"})

    physical = None
    if calibration is not None:
        physical = _to_physical(pixel, calibration.pixels_per_mm)
        for component in components:
            component["physical"] = _to_physical(component, calibration.pixels_per_mm)
    return MeasurementResult(basis, "MEASURED", pixel, physical, components, confidence, calibration_dict,
                             warnings, full_provenance, units=units)
