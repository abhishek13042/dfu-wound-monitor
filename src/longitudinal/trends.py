"""P04-S03 technical trend outputs.

``build_trend`` turns the stored examinations of **one** case into an ordered
series of image-derived measurements, measured against the first compatible
examination (the baseline) and against the previous one.

* Only compatible measurements are used (REQ-P04-S03-001).  Excluded
  examinations are listed with their reason codes, never silently dropped.
* A zero baseline gives ``percent_change: None`` with state ``BASELINE_ZERO``;
  fewer than two usable points gives ``status: UNAVAILABLE``
  (REQ-P04-S03-002).
* Every output carries the technical-trend label (REQ-P04-S03-003).
* ``trend_id`` is a hash of the inputs and policy, so the same records always
  give the same artifact (REQ-P04-S03-004).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from src.longitudinal.comparison import (
    AVAILABLE,
    METRICS,
    UNAVAILABLE,
    CompatibilityPolicy,
    MeasurementPoint,
    canonical_hash,
    carried_warnings,
    change,
    elapsed_days,
    metric_values,
    pair_problems,
    point_problems,
)

TREND_LABEL = ("Image-derived technical trend of the segmented region. Not a clinical assessment of healing, "
               "prognosis or treatment response.")
TREND_VERSION = "p04-s03-v1"


@dataclass
class TrendResult:
    status: str
    case_id: str | None
    basis: str | None
    unit: dict[str, str]
    rows: list[dict[str, Any]]
    excluded: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    reason_codes: list[str]
    policy: dict[str, Any]
    trend_id: str
    version: str = TREND_VERSION
    label: str = TREND_LABEL

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_csv(self) -> str:
        buffer = io.StringIO()
        columns = ["examination_id", "analysis_id", "captured_at", "days_since_baseline", "area",
                   "area_change_from_baseline", "area_percent_change_from_baseline", "area_change_from_previous",
                   "perimeter", "max_feret", "flags"]
        writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
        buffer.write(f"# {self.label}\n# basis={self.basis} area_unit={self.unit.get('area')} trend_id={self.trend_id}\n")
        writer.writeheader()
        for row in self.rows:
            writer.writerow({
                "examination_id": row["examination_id"], "analysis_id": row["analysis_id"],
                "captured_at": row["captured_at"], "days_since_baseline": row["days_since_baseline"],
                "area": row["values"]["area"],
                "area_change_from_baseline": row["from_baseline"]["area"]["absolute_change"],
                "area_percent_change_from_baseline": row["from_baseline"]["area"]["percent_change"],
                "area_change_from_previous": (row["from_previous"] or {}).get("area", {}).get("absolute_change"),
                "perimeter": row["values"]["perimeter"], "max_feret": row["values"]["max_feret"],
                "flags": "|".join(row["flags"]),
            })
        return buffer.getvalue()

    def to_markdown(self) -> str:
        lines = [f"**{self.label}**", "",
                 f"Case `{self.case_id}` - basis `{self.basis}` - status `{self.status}` - trend `{self.trend_id[:12]}`", ""]
        if self.rows:
            unit = self.unit.get("area", "")
            lines += [f"| Captured | Days | Area ({unit}) | Change vs baseline | % vs baseline | Flags |",
                      "|---|---:|---:|---:|---:|---|"]
            for row in self.rows:
                base = row["from_baseline"]["area"]
                pct = "n/a" if base["percent_change"] is None else f"{base['percent_change']:+.1f}%"
                lines.append(f"| {row['captured_at']} | {row['days_since_baseline']:.1f} | {row['values']['area']:.2f} "
                             f"| {base['absolute_change']:+.2f} | {pct} | {', '.join(row['flags']) or '-'} |")
        for item in self.excluded:
            lines.append(f"- Excluded `{item['examination_id']}`: {', '.join(item['reason_codes'])}")
        for warning in self.warnings:
            lines.append(f"- Warning `{warning['code']}`: {warning.get('message', '')}")
        return "\n".join(lines) + "\n"

    def plot(self, path: Path) -> Path:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        figure, axis = plt.subplots(figsize=(7, 3.6), dpi=120)
        days = [row["days_since_baseline"] for row in self.rows]
        areas = [row["values"]["area"] for row in self.rows]
        axis.plot(days, areas, marker="o", color="#2563eb")
        for row, x, y in zip(self.rows, days, areas):
            if row["flags"]:
                axis.annotate("!", (x, y), textcoords="offset points", xytext=(0, 6), ha="center", color="#b45309")
        axis.set_xlabel("Days since baseline examination")
        axis.set_ylabel(f"Segmented area ({self.unit.get('area')})")
        axis.set_title("Image-derived technical trend (not a clinical assessment)", fontsize=10)
        axis.grid(alpha=0.3)
        figure.tight_layout()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(path, metadata={"Software": None})
        plt.close(figure)
        return path


def _sort_key(point: MeasurementPoint):
    return (point.examination.captured_at.isoformat() if point.examination.captured_at else "",
            point.examination.examination_id, point.analysis.analysis_id)


def build_trend(points: Sequence[MeasurementPoint], policy: CompatibilityPolicy | None = None) -> TrendResult:
    if policy is None:
        raise ValueError("A CompatibilityPolicy is required to build a trend")
    ordered = sorted(points, key=_sort_key)
    source = [{"analysis_id": p.analysis.analysis_id, "examination_id": p.examination.examination_id,
               "case_id": p.case.case_id, "captured_at": p.examination.captured_at, "identity": p.case.identity_status,
               "model_version": p.analysis.model_version, "measurement": p.analysis.measurement,
               "calibration": p.analysis.calibration} for p in ordered]
    trend_id = canonical_hash({"version": TREND_VERSION, "policy": policy.to_dict(), "points": source})
    case_ids = sorted({p.case.case_id for p in ordered})
    if len(case_ids) > 1:
        return TrendResult(UNAVAILABLE, None, None, {}, [], [], [], ["MIXED_CASES"], policy.to_dict(), trend_id)

    excluded: list[dict[str, Any]] = []
    usable: list[MeasurementPoint] = []
    for point in ordered:
        problems = point_problems(point, policy)
        if not problems and usable:
            problems = pair_problems(usable[0], point, policy)
            if "SAME_TIMESTAMP" not in problems and point.examination.captured_at == usable[-1].examination.captured_at:
                problems.append("SAME_TIMESTAMP")
        if problems:
            excluded.append({"examination_id": point.examination.examination_id,
                             "analysis_id": point.analysis.analysis_id, "reason_codes": problems})
        else:
            usable.append(point)

    case_id = case_ids[0] if case_ids else None
    if len(usable) < 2:
        reasons = ["INSUFFICIENT_POINTS"] + (["NO_BASELINE"] if not usable else [])
        return TrendResult(UNAVAILABLE, case_id, None, {}, [], excluded, [], reasons, policy.to_dict(), trend_id)

    basis = cast(str, usable[0].analysis.measurement_basis)
    unit_index = 3 if basis == "PHYSICALLY_CALIBRATED" else 2
    unit = {name: keys[unit_index] for name, keys in METRICS.items()}
    warnings: list[dict[str, Any]] = []
    if basis == "PIXEL_BASED":
        warnings.append({"code": "PIXEL_SCALE_NOT_CONTROLLED",
                         "message": "No calibration: pixel changes also reflect camera distance and zoom"})
    if excluded:
        warnings.append({"code": "EXAMINATIONS_EXCLUDED", "message": f"{len(excluded)} examination(s) not used"})

    baseline = usable[0]
    base_values = metric_values(baseline, basis)
    rows, previous = [], None
    for point in usable:
        values = metric_values(point, basis)
        days = elapsed_days(baseline, point)
        flags = [w["code"] for w in carried_warnings(point, "point")]
        from_baseline = {name: change(base_values[name], values[name]) for name in METRICS}
        if from_baseline["area"]["state"] == "BASELINE_ZERO" and "BASELINE_ZERO" not in flags and point is not baseline:
            flags.append("BASELINE_ZERO")
        from_previous = None
        if previous is not None:
            prev_values = metric_values(previous, basis)
            from_previous = {name: change(prev_values[name], values[name]) for name in METRICS}
            gap = elapsed_days(previous, point)
            if gap > policy.max_gap_days:
                flags.append("LONG_GAP")
                warnings.append({"code": "LONG_GAP", "examination_id": point.examination.examination_id,
                                 "message": f"{gap:.1f} days since the previous usable examination (missing visits?)"})
        rows.append({
            "examination_id": point.examination.examination_id,
            "analysis_id": point.analysis.analysis_id,
            "captured_at": cast(datetime, point.examination.captured_at).isoformat(),
            "days_since_baseline": round(days, 4),
            "is_baseline": point is baseline,
            "model_version": point.analysis.model_version,
            "values": values,
            "from_baseline": from_baseline,
            "from_previous": from_previous,
            "flags": flags,
        })
        previous = point
    if base_values["area"] == 0:
        warnings.append({"code": "BASELINE_ZERO", "message": "Baseline area is zero; percentage changes are undefined"})
    return TrendResult(AVAILABLE, case_id, basis, unit, rows, excluded, warnings, [], policy.to_dict(), trend_id)
