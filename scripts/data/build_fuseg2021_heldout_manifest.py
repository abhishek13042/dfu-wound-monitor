"""Build the SPEC-02-03 held-out FUSeg2021 manifest from the official manifest.

Official validation becomes the held-out test split.  A seeded,
near-duplicate-group-aware internal validation split is carved from official
train.  Raw data and the official manifest are not modified.

    python scripts/data/build_fuseg2021_heldout_manifest.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.data.heldout_split import derive_heldout_manifest, sample_key  # noqa: E402
from src.data.near_duplicates import (  # noqa: E402
    DEFAULT_MAX_HAMMING_DISTANCE,
    compute_phash_for_path,
)
from src.data.splitting import verify_split_leakage  # noqa: E402
from src.segmentation.dataset import resolve_manifest_path  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="data/manifests/dataset_manifest.json")
    parser.add_argument("--output", default="data/manifests/fuseg2021_heldout_manifest.json")
    parser.add_argument("--report", default="data/manifests/fuseg2021_heldout_split_report.json")
    parser.add_argument("--internal-val-fraction", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-hamming", type=int, default=DEFAULT_MAX_HAMMING_DISTANCE)
    args = parser.parse_args()

    manifest_path = project_root / args.manifest
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    phashes = {}
    for record in manifest["samples"]:
        if record.get("validation_status") != "VALID" or record.get("annotation_type") != "wound_segmentation":
            continue
        image_path = resolve_manifest_path(record["image_path"], str(manifest_path))
        phashes[sample_key(record)] = compute_phash_for_path(image_path)

    derived, report = derive_heldout_manifest(
        manifest,
        phashes,
        internal_val_fraction=args.internal_val_fraction,
        seed=args.seed,
        max_hamming_distance=args.max_hamming,
    )
    leakage = verify_split_leakage(
        [record for record in derived["samples"] if record["validation_status"] == "VALID"]
    )
    derived["split_summary"]["leakage_analysis"] = leakage
    report["exact_leakage_analysis"] = leakage
    if not leakage["leakage_test_passed"]:
        raise RuntimeError(f"Held-out manifest failed exact leakage checks: {leakage}")

    (project_root / args.output).write_text(json.dumps(derived, indent=2) + "\n", encoding="utf-8")
    (project_root / args.report).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"Held-out manifest written: train={report['counts']['train']}, "
        f"internal_val={report['counts']['val']}, heldout_test={report['counts']['test']}, "
        f"near_dup_pairs={report['near_duplicate_pairs']}, "
        f"quarantined_near_test={len(report['train_quarantined_near_duplicate_of_test'])}"
    )


if __name__ == "__main__":
    main()
