"""P10-S04: build the input-drift reference from the FUSeg2021 held-out test split.

The quality measures come from running the quality gate on each test image;
the predicted area comes from the P06 validation report for the active model,
so no model is run.  Each sample becomes the same summary row a stored
analysis gives (``src.mlops.drift.features_from_record``).

    python scripts/monitoring/build_drift_reference.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.mlops.drift import build_reference, features_from_record  # noqa: E402
from src.quality.gate import QualityGate  # noqa: E402

DEFAULT_OUTPUT = PROJECT_ROOT / "configs/models/drift_reference_fuseg2021.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--manifest", type=Path, default=PROJECT_ROOT / "data/manifests/fuseg2021_heldout_manifest.json")
    parser.add_argument("--validation", type=Path,
                        default=PROJECT_ROOT / "reports/final/p06_validation_fuseg2021_test.json")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    validation = json.loads(args.validation.read_text(encoding="utf-8"))
    predicted = {row["sample_id"]: row for row in validation["per_sample"]}
    gate = QualityGate()
    rows = []
    for sample in manifest["samples"]:
        if sample["split"] != "test":
            continue
        quality = gate.evaluate((PROJECT_ROOT / sample["image_path"]).read_bytes()).to_dict()
        measured = quality["measurements"]
        record = {"status": "COMPLETED" if quality["status"] == "ACCEPTED" else "QUALITY_REJECTED",
                  "quality": quality,
                  "provenance": {"input": {"width": measured.get("width"), "height": measured.get("height")}}}
        pred = (predicted.get(sample["source_sample_id"]) or {}).get("pred")
        if record["status"] == "COMPLETED" and pred is not None:
            # P06 scored masks at the model's 512 x 512 working size.
            record["measurement"] = {"pixel": {"area_px": pred["area_px"]},
                                     "provenance": {"measurement": {"mask_shape": [512, 512]}}}
        rows.append(features_from_record(record))

    reference = build_reference(rows, source=f"{manifest['manifest_version']} test split ({len(rows)} images); "
                                             f"predicted area from {args.validation.relative_to(PROJECT_ROOT).as_posix()}")
    reference["model_version"] = validation["provenance"]["model"]["model_version"]
    args.output.write_text(json.dumps(reference, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} from {len(rows)} images: features {sorted(reference['features'])}, "
          f"rejection rate {reference['quality_rejection_rate']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
