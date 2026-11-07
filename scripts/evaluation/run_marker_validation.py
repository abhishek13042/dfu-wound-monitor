"""REQ-P09-S01-003: measure marker-scale error on objects of known size.

Two modes, written to different reports so a synthetic run is never mistaken for the real one:

    python scripts/evaluation/run_marker_validation.py --data photos/manifest.json
        -> reports/final/p09_s01_marker_validation.json
    python scripts/evaluation/run_marker_validation.py --synthetic
        -> reports/final/p09_s01_marker_validation_synthetic.json

The manifest lists real photos of a printed marker beside an object of known length:

    {"images": [{"path": "IMG_0001.jpg", "distance_cm": 30, "angle_deg": 0,
                 "object": {"p1": [412, 300], "p2": [1012, 304], "true_mm": 60.0}}]}

Paths are relative to the manifest. ``p1`` and ``p2`` are the object's end points in image pixels, marked by hand.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.measurement.marker import MarkerConfig, detect_marker  # noqa: E402
from src.measurement.marker_synthetic import render_scene  # noqa: E402

TARGET_MEDIAN_ABS_ERROR_PCT = 3.0


def _row(reading, p1, p2, true_mm: float, **condition) -> dict[str, Any]:
    row: dict[str, Any] = {**condition, "status": reading.status}
    if reading.found:
        length_px = float(np.hypot(p2[0] - p1[0], p2[1] - p1[1]))
        estimate = length_px / reading.calibration.pixels_per_mm
        row.update(pixels_per_mm=round(reading.calibration.pixels_per_mm, 4),
                   uncertainty_pct=reading.calibration.uncertainty_pct,
                   estimated_mm=round(estimate, 3), true_mm=true_mm,
                   error_pct=round((estimate - true_mm) / true_mm * 100, 3))
    return row


def _summary(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    groups: dict[Any, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(row[key], []).append(row)
    out = []
    for value, group in sorted(groups.items()):
        errors = [abs(r["error_pct"]) for r in group if "error_pct" in r]
        statuses: dict[str, int] = {}
        for r in group:
            statuses[r["status"]] = statuses.get(r["status"], 0) + 1
        out.append({key: value, "images": len(group), "accepted": len(errors), "statuses": statuses,
                    "median_abs_error_pct": round(statistics.median(errors), 3) if errors else None,
                    "max_abs_error_pct": round(max(errors), 3) if errors else None})
    return out


def run_synthetic(config: MarkerConfig) -> dict[str, Any]:
    rows = []
    for px_per_mm in (2.5, 3.5, 5.0, 7.0):
        for tilt in (0, 10, 20, 30):
            for seed in range(3):
                scene = render_scene(px_per_mm=px_per_mm, tilt_deg=tilt, image_size=(1280, 960), noise=5,
                                     seed=seed, marker_id=config.marker_id, dictionary=config.dictionary,
                                     marker_mm=config.side_mm, textured_background=True)
                reading = detect_marker(scene.image, config)
                rows.append(_row(reading, *scene.bar_px, scene.bar_mm, px_per_mm=px_per_mm, tilt_deg=tilt, seed=seed))
    return {"mode": "SYNTHETIC",
            "label": ("Synthetic renders of a flat sheet through an ideal pinhole camera. They check the geometry code; "
                      "they say nothing about real printers, lenses, lighting or skin. REQ-P09-S01-003 needs real photos."),
            "rows": rows, "by_tilt_deg": _summary(rows, "tilt_deg"), "by_px_per_mm": _summary(rows, "px_per_mm")}


def run_data(manifest_path: Path, config: MarkerConfig) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = []
    for entry in manifest["images"]:
        image = ImageOps.exif_transpose(Image.open(manifest_path.parent / entry["path"])).convert("RGB")
        reading = detect_marker(np.asarray(image), config)
        target = entry["object"]
        rows.append(_row(reading, target["p1"], target["p2"], float(target["true_mm"]), image=entry["path"],
                         distance_cm=entry.get("distance_cm"), angle_deg=entry.get("angle_deg")))
    return {"mode": "REAL_PHOTOS", "manifest": str(manifest_path), "rows": rows,
            "by_angle_deg": _summary(rows, "angle_deg"), "by_distance_cm": _summary(rows, "distance_cm")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--data", type=Path, help="manifest of real marker photos")
    group.add_argument("--synthetic", action="store_true")
    parser.add_argument("--config", default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    config = MarkerConfig.load(args.config) if args.config else MarkerConfig.load()
    report = run_synthetic(config) if args.synthetic else run_data(args.data, config)
    accepted = [abs(r["error_pct"]) for r in report["rows"] if "error_pct" in r]
    median = round(statistics.median(accepted), 3) if accepted else None
    report = {"spec": "P09-S01", "requirement": "REQ-P09-S01-003", "created_at": datetime.now(UTC).isoformat(),
              "marker_config": config.reference(), **report,
              "overall": {"images": len(report["rows"]), "accepted": len(accepted), "median_abs_error_pct": median,
                          "target_median_abs_error_pct": TARGET_MEDIAN_ABS_ERROR_PCT,
                          "target_met": median is not None and median <= TARGET_MEDIAN_ABS_ERROR_PCT}}
    name = "p09_s01_marker_validation_synthetic.json" if args.synthetic else "p09_s01_marker_validation.json"
    out = args.out or ROOT / "reports" / "final" / name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), **report["overall"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
