"""Measure P03-S02 quality signals over real datasets to calibrate gate thresholds.

The gate's job is to reject technically unusable photos, not curated dataset
images.  Thresholds are therefore set beyond the observed range of the real
FUSeg2021 and LowerLimb V3 images.  This script records those distributions.

    python scripts/evaluation/calibrate_quality_gate.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.quality.gate import QualityGate  # noqa: E402
from src.quality.measures import measure_quality  # noqa: E402

FUSEG = PROJECT_ROOT / "data/raw/FUSeg2021/source/data/Foot Ulcer Segmentation Challenge"
SOURCES = {
    "fuseg2021_train": FUSEG / "train/images",
    "fuseg2021_validation": FUSEG / "validation/images",
    "lowerlimb_v3": PROJECT_ROOT / "data/raw/LowerLimbFeetWound/V3/extracted/wound_main",
}
OUTPUT = PROJECT_ROOT / "reports/quality/quality_gate_calibration.json"
PERCENTILES = (0, 0.5, 1, 5, 50, 95, 99, 99.5, 100)


def main() -> None:
    gate = QualityGate()
    report = {"description": __doc__.strip().splitlines()[0], "quality_config": gate.config.reference(),
              "percentiles": list(PERCENTILES), "sources": {}}
    for name, folder in SOURCES.items():
        paths = sorted(p for p in folder.glob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg"})
        rows, rejected = [], []
        for path in paths:
            with Image.open(path) as handle:
                rows.append(measure_quality(handle, gate.config.analysis_size))
            status, reasons, _ = gate._decide(rows[-1])
            if reasons:
                rejected.append({"image": path.name, "reason_codes": reasons})
        keys = rows[0].keys()
        report["sources"][name] = {
            "folder": str(folder.relative_to(PROJECT_ROOT)),
            "num_images": len(rows),
            "rejected_by_gate": len(rejected),
            "rejections": rejected,
            "measures": {key: [round(float(np.percentile([r[key] for r in rows], q)), 4) for q in PERCENTILES]
                         for key in keys},
        }
        print(name, len(rows), "rejected", len(rejected), rejected[:10])
        for key in keys:
            print(f"  {key:20s}", report["sources"][name]["measures"][key])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("wrote", OUTPUT)


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    main()
