"""P10-S04 input drift (REQ-P10-S04-004, REQ-P10-S04-005).

Compares recent analyses with a stored reference on summary numbers the
service already keeps: brightness, blur, image size, predicted area as a share
of the image, and the quality-rejection rate.  No image is read, so the check
can run on the analyses table alone.

Each numeric feature is compared with the population stability index (PSI)
over the reference's own quantile bins.  The rejection rate is compared as a
difference in proportions.  A drift alert says the *inputs* changed; it never
claims accuracy changed, because no ground truth exists in production.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np

FEATURES = ("mean_luminance", "laplacian_variance", "megapixels", "predicted_area_share")
BINS = 10
PSI_MODERATE = 0.10
PSI_SHIFT = 0.25
REJECTION_RATE_SHIFT = 0.10   # absolute change in the share of images the quality gate rejects
MIN_SAMPLES = 50
REFERENCE_MAX_AGE = timedelta(days=180)
EPSILON = 1e-4
ALERT_TEXT = ("The images coming in have changed compared with the reference set. This is a change in inputs, "
              "not a measured change in accuracy: there is no ground truth in production. Review a sample of "
              "recent images before drawing conclusions about the model.")


def features_from_record(record: dict[str, Any]) -> dict[str, Any]:
    """Pull the summary numbers out of a stored analysis record (``AnalysisRecord`` as a dict)."""

    measured = (record.get("quality") or {}).get("measurements") or {}
    size = (record.get("provenance") or {}).get("input") or {}
    width, height = size.get("width") or measured.get("width"), size.get("height") or measured.get("height")
    row: dict[str, Any] = {"status": record.get("status"),
                           "mean_luminance": measured.get("mean_luminance"),
                           "laplacian_variance": measured.get("laplacian_variance"),
                           "megapixels": width * height / 1e6 if width and height else None,
                           "predicted_area_share": None}
    measurement = record.get("measurement") or {}
    area = (measurement.get("pixel") or {}).get("area_px")
    shape = ((measurement.get("provenance") or {}).get("measurement") or {}).get("mask_shape")
    if area is not None and shape:
        row["predicted_area_share"] = area / (shape[0] * shape[1])
    return row


def _values(rows: Iterable[dict[str, Any]], feature: str) -> np.ndarray:
    values = [row[feature] for row in rows if row.get(feature) is not None and math.isfinite(row[feature])]
    return np.asarray(values, dtype=np.float64)


def _rejection_rate(rows: list[dict[str, Any]]) -> float | None:
    judged = [row for row in rows if row.get("status") in ("COMPLETED", "QUALITY_REJECTED")]
    if not judged:
        return None
    return sum(row["status"] == "QUALITY_REJECTED" for row in judged) / len(judged)


def build_reference(rows: list[dict[str, Any]], source: str) -> dict[str, Any]:
    features = {}
    for feature in FEATURES:
        values = _values(rows, feature)
        if len(values) < MIN_SAMPLES:
            continue
        # Inner quantile edges; the outer bins are open so new extremes still land somewhere.
        edges = np.unique(np.quantile(values, np.linspace(0, 1, BINS + 1)[1:-1]))
        counts = np.bincount(np.searchsorted(edges, values, side="right"), minlength=len(edges) + 1)
        features[feature] = {"n": int(len(values)), "edges": [round(float(e), 6) for e in edges],
                             "proportions": [round(float(c) / len(values), 6) for c in counts],
                             "median": round(float(np.median(values)), 6)}
    return {"schema": "p10-s04-drift-reference-v1", "source": source,
            "built_at": datetime.now(UTC).isoformat(timespec="seconds"), "n": len(rows),
            "quality_rejection_rate": _rejection_rate(rows), "features": features}


def psi(reference: dict[str, Any], values: np.ndarray) -> float:
    edges = np.asarray(reference["edges"], dtype=np.float64)
    expected = np.asarray(reference["proportions"], dtype=np.float64)
    actual = np.bincount(np.searchsorted(edges, values, side="right"), minlength=len(edges) + 1) / len(values)
    expected, actual = np.clip(expected, EPSILON, None), np.clip(actual, EPSILON, None)
    return float(np.sum((actual - expected) * np.log(actual / expected)))


def _level(value: float) -> str:
    return "SHIFT" if value >= PSI_SHIFT else "MODERATE" if value >= PSI_MODERATE else "STABLE"


def check(reference: dict[str, Any], rows: list[dict[str, Any]], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    report: dict[str, Any] = {"checked_at": now.isoformat(timespec="seconds"), "samples": len(rows),
                              "reference": {"source": reference["source"], "built_at": reference["built_at"],
                                            "n": reference["n"]},
                              "thresholds": {"psi_moderate": PSI_MODERATE, "psi_shift": PSI_SHIFT,
                                             "rejection_rate_shift": REJECTION_RATE_SHIFT,
                                             "min_samples": MIN_SAMPLES},
                              "features": {}, "notes": []}
    built = datetime.fromisoformat(reference["built_at"])
    if now - built > REFERENCE_MAX_AGE:
        report["notes"].append(f"The reference is older than {REFERENCE_MAX_AGE.days} days; rebuild it")

    shifted = []
    for feature, ref in reference["features"].items():
        values = _values(rows, feature)
        if len(values) < MIN_SAMPLES:
            report["features"][feature] = {"status": "INSUFFICIENT_DATA", "n": int(len(values))}
            continue
        value = psi(ref, values)
        level = _level(value)
        report["features"][feature] = {"status": level, "psi": round(value, 4), "n": int(len(values)),
                                       "median": round(float(np.median(values)), 6),
                                       "reference_median": ref["median"]}
        if level == "SHIFT":
            shifted.append(feature)

    rate, ref_rate = _rejection_rate(rows), reference.get("quality_rejection_rate")
    judged = sum(row.get("status") in ("COMPLETED", "QUALITY_REJECTED") for row in rows)
    if rate is None or ref_rate is None or judged < MIN_SAMPLES:
        report["features"]["quality_rejection_rate"] = {"status": "INSUFFICIENT_DATA", "n": judged}
    else:
        change = rate - ref_rate
        level = "SHIFT" if abs(change) >= REJECTION_RATE_SHIFT else "STABLE"
        report["features"]["quality_rejection_rate"] = {"status": level, "rate": round(rate, 4),
                                                        "reference_rate": round(ref_rate, 4),
                                                        "change": round(change, 4), "n": judged}
        if level == "SHIFT":
            shifted.append("quality_rejection_rate")

    statuses = {row["status"] for row in report["features"].values()}
    if shifted:
        report["status"], report["alert"] = "DRIFT", {"kind": "INPUT_DRIFT", "features": shifted,
                                                      "message": ALERT_TEXT}
    elif statuses == {"INSUFFICIENT_DATA"}:
        report["status"] = "INSUFFICIENT_DATA"
    else:
        report["status"] = "STABLE"
    return report
