"""P04-S02 multi-examination compatibility and pairwise comparison.

A comparison is ``AVAILABLE`` only when the compatibility policy holds
(REQ-P04-S02-001).  Otherwise it is ``UNAVAILABLE`` with explicit reason codes
and no change values (REQ-P04-S02-002).  The same case and a verified identity
are always required: public-dataset samples are never linked into a patient
trajectory (REQ-P04-S02-004).

Unavailable reasons:

``CASE_UNKNOWN``                 an examination has no case
``CASE_MISMATCH``                examination.case_id differs from the case record
``DIFFERENT_CASE``               the two points belong to different cases
``IDENTITY_UNVERIFIED``          the case identity is not VERIFIED
``TIMESTAMP_MISSING``            an examination has no capture time
``SAME_TIMESTAMP``               both examinations have the same capture time
``MEASUREMENT_MISSING``          an analysis has no measurement (rejected/failed)
``MODEL_VERSION_MISMATCH``       different model versions produced the masks
``MEASUREMENT_BASIS_MISMATCH``   one point is calibrated and the other is not
``PIXEL_COMPARISON_DISALLOWED``  pixel-only points and the policy forbids it
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.longitudinal.records import AnalysisRecord, CaseRecord, ExaminationRecord

AVAILABLE, UNAVAILABLE = "AVAILABLE", "UNAVAILABLE"
TECHNICAL_LABEL = ("Image-derived technical comparison of segmented regions. It is not a clinical assessment of "
                   "healing and must not be used for diagnosis or treatment decisions.")
# metric name -> (pixel key, physical key, pixel unit, physical unit)
METRICS = {
    "area": ("area_px", "area_mm2", "px^2", "mm^2"),
    "perimeter": ("perimeter_px", "perimeter_mm", "px", "mm"),
    "max_feret": ("max_feret_px", "max_feret_mm", "px", "mm"),
    "min_feret": ("min_feret_px", "min_feret_mm", "px", "mm"),
}
CARRIED_WARNINGS = ("LOW_CONFIDENCE", "TOUCHES_IMAGE_BORDER", "MULTIPLE_COMPONENTS", "SMALL_REGION", "EMPTY_MASK",
                    "THRESHOLD_OVERRIDE")


@dataclass(frozen=True)
class CompatibilityPolicy:
    version: str = "p04-s02-v1"
    require_verified_identity: bool = True
    require_same_model_version: bool = True
    allow_pixel_comparison: bool = True
    calibration_change_warn_pct: float = 5.0
    max_gap_days: float = 60.0

    def __post_init__(self) -> None:
        if self.calibration_change_warn_pct < 0 or self.max_gap_days <= 0:
            raise ValueError("calibration_change_warn_pct must be >= 0 and max_gap_days > 0")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MeasurementPoint:
    case: CaseRecord
    examination: ExaminationRecord
    analysis: AnalysisRecord

    def reference(self) -> Dict[str, Any]:
        return {
            "case_id": self.case.case_id,
            "examination_id": self.examination.examination_id,
            "image_id": self.analysis.image_id,
            "analysis_id": self.analysis.analysis_id,
            "captured_at": self.examination.captured_at.isoformat() if self.examination.captured_at else None,
            "model_version": self.analysis.model_version,
            "measurement_basis": self.analysis.measurement_basis,
        }


@dataclass
class ComparisonResult:
    status: str
    reason_codes: List[str]
    warnings: List[Dict[str, Any]]
    earlier: Dict[str, Any]
    later: Dict[str, Any]
    basis: Optional[str]
    interval_days: Optional[float]
    metrics: Dict[str, Dict[str, Any]]
    policy: Dict[str, Any]
    label: str = TECHNICAL_LABEL

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def point_problems(point: MeasurementPoint, policy: CompatibilityPolicy) -> List[str]:
    """Reasons a single point cannot take part in any comparison."""

    problems = []
    exam_case = point.examination.case_id
    if exam_case is None:
        problems.append("CASE_UNKNOWN")
    elif exam_case != point.case.case_id:
        problems.append("CASE_MISMATCH")
    if policy.require_verified_identity and point.case.identity_status != "VERIFIED":
        problems.append("IDENTITY_UNVERIFIED")
    if point.examination.captured_at is None:
        problems.append("TIMESTAMP_MISSING")
    if point.analysis.status != "COMPLETED" or point.analysis.measurement is None:
        problems.append("MEASUREMENT_MISSING")
    if point.analysis.examination_id not in (None, point.examination.examination_id):
        problems.append("CASE_MISMATCH")
    return list(dict.fromkeys(problems))


def pair_problems(a: MeasurementPoint, b: MeasurementPoint, policy: CompatibilityPolicy) -> List[str]:
    problems = []
    if a.case.case_id != b.case.case_id:
        problems.append("DIFFERENT_CASE")
    if a.examination.captured_at and b.examination.captured_at and a.examination.captured_at == b.examination.captured_at:
        problems.append("SAME_TIMESTAMP")
    if policy.require_same_model_version and a.analysis.model_version != b.analysis.model_version:
        problems.append("MODEL_VERSION_MISMATCH")
    basis_a, basis_b = a.analysis.measurement_basis, b.analysis.measurement_basis
    if basis_a and basis_b:
        if basis_a != basis_b:
            problems.append("MEASUREMENT_BASIS_MISMATCH")
        elif basis_a == "PIXEL_BASED" and not policy.allow_pixel_comparison:
            problems.append("PIXEL_COMPARISON_DISALLOWED")
    return problems


def metric_values(point: MeasurementPoint, basis: str) -> Dict[str, Optional[float]]:
    measurement = point.analysis.measurement or {}
    section = measurement.get("physical") if basis == "PHYSICALLY_CALIBRATED" else measurement.get("pixel")
    section = section or {}
    index = 1 if basis == "PHYSICALLY_CALIBRATED" else 0
    values = {}
    for name, keys in METRICS.items():
        value = section.get(keys[index])
        if value is None and measurement.get("status") == "EMPTY" and name in ("area", "perimeter"):
            value = 0.0
        values[name] = None if value is None else float(value)
    return values


def change(earlier: Optional[float], later: Optional[float]) -> Dict[str, Any]:
    if earlier is None or later is None:
        return {"earlier": earlier, "later": later, "absolute_change": None, "percent_change": None,
                "state": "MISSING"}
    absolute = round(later - earlier, 6)
    if earlier == 0:
        return {"earlier": earlier, "later": later, "absolute_change": absolute, "percent_change": None,
                "state": "BASELINE_ZERO"}
    return {"earlier": earlier, "later": later, "absolute_change": absolute,
            "percent_change": round(100.0 * (later - earlier) / earlier, 4), "state": "OK"}


def carried_warnings(point: MeasurementPoint, role: str) -> List[Dict[str, Any]]:
    out = []
    for warning in point.analysis.warnings + (point.analysis.measurement or {}).get("warnings", []):
        if warning.get("code") in CARRIED_WARNINGS:
            item = {"code": warning["code"], "source": role, "analysis_id": point.analysis.analysis_id}
            if item not in out:
                out.append(item)
    return out


def calibration_warnings(a: MeasurementPoint, b: MeasurementPoint, policy: CompatibilityPolicy) -> List[Dict[str, Any]]:
    cal_a, cal_b = a.analysis.calibration, b.analysis.calibration
    if not cal_a or not cal_b:
        return []
    warnings = []
    if cal_a.get("method") != cal_b.get("method"):
        warnings.append({"code": "CALIBRATION_METHOD_CHANGED",
                         "message": f"{cal_a.get('method')} -> {cal_b.get('method')}"})
    ppm_a, ppm_b = float(cal_a["pixels_per_mm"]), float(cal_b["pixels_per_mm"])
    delta = abs(ppm_b - ppm_a) / ppm_a * 100.0
    if delta > policy.calibration_change_warn_pct:
        warnings.append({"code": "CALIBRATION_CHANGED",
                         "message": f"Scale changed by {delta:.1f}% (camera distance or zoom differs); "
                                    "mm values are comparable only if both calibrations are correct",
                         "change_pct": round(delta, 3)})
    return warnings


def order(a: MeasurementPoint, b: MeasurementPoint) -> Tuple[MeasurementPoint, MeasurementPoint]:
    ta, tb = a.examination.captured_at, b.examination.captured_at
    if ta and tb and tb < ta:
        return b, a
    return a, b


def compare(a: MeasurementPoint, b: MeasurementPoint,
            policy: Optional[CompatibilityPolicy] = None) -> ComparisonResult:
    """Compare two examinations; the earlier capture becomes the reference."""

    if policy is None:
        raise ValueError("A CompatibilityPolicy is required for every comparison")
    earlier, later = order(a, b)
    reasons = list(dict.fromkeys(point_problems(earlier, policy) + point_problems(later, policy)
                                 + pair_problems(earlier, later, policy)))
    refs = (earlier.reference(), later.reference())
    if reasons:
        return ComparisonResult(UNAVAILABLE, reasons, [], *refs, None, None, {}, policy.to_dict())

    basis = earlier.analysis.measurement_basis
    warnings: List[Dict[str, Any]] = []
    if basis == "PIXEL_BASED":
        warnings.append({"code": "PIXEL_SCALE_NOT_CONTROLLED",
                         "message": "No calibration: pixel changes also reflect camera distance and zoom"})
    warnings += calibration_warnings(earlier, later, policy)
    warnings += carried_warnings(earlier, "earlier") + carried_warnings(later, "later")
    values_a, values_b = metric_values(earlier, basis), metric_values(later, basis)
    unit_index = 3 if basis == "PHYSICALLY_CALIBRATED" else 2
    metrics = {name: {**change(values_a[name], values_b[name]), "unit": METRICS[name][unit_index]}
               for name in METRICS}
    if metrics["area"]["state"] == "BASELINE_ZERO":
        warnings.append({"code": "BASELINE_ZERO", "message": "Earlier area is zero; percentage change is undefined"})
    gap = (later.examination.captured_at - earlier.examination.captured_at).total_seconds() / 86400.0
    if gap > policy.max_gap_days:
        warnings.append({"code": "LONG_INTERVAL", "message": f"{gap:.1f} days between examinations"})
    return ComparisonResult(AVAILABLE, [], warnings, *refs, basis, round(gap, 4), metrics, policy.to_dict())


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
