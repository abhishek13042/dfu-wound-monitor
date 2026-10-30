"""Build the verified FUSeg2021 Phase 02 manifest without re-splitting data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.data.fuseg import build_fuseg_manifest  # noqa: E402
from src.data.splitting import verify_split_leakage  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path("data/raw/FUSeg2021/source/data/Foot Ulcer Segmentation Challenge"),
        help="Official FUSeg2021 source directory containing train/validation/test.",
    )
    parser.add_argument(
        "--dataset-version",
        default="FUSeg2021-official-source-commit-42a272d",
    )
    parser.add_argument(
        "--source-commit",
        default="42a272dfe0679f20675e826385925cb7562934b6",
    )
    parser.add_argument(
        "--source-content-digest",
        default="6631246d6128a8d0167d9fb63abbbb2ec1fae4c4b19b4917caf2f94625972b17",
    )
    args = parser.parse_args()

    source_root = args.source_root if args.source_root.is_absolute() else project_root / args.source_root
    manifest, quality_report = build_fuseg_manifest(
        source_root=source_root,
        project_root=project_root,
        dataset_version=args.dataset_version,
        source_commit=args.source_commit,
        source_content_digest=args.source_content_digest,
    )

    leakage_records = [
        record
        for record in manifest["samples"]
        if record["validation_status"] == "VALID"
    ]
    leakage_report = verify_split_leakage(leakage_records)
    manifest["split_summary"]["leakage_analysis"] = leakage_report
    quality_report["leakage_analysis"] = leakage_report
    if not leakage_report["leakage_test_passed"]:
        raise RuntimeError(
            "FUSeg2021 manifest construction failed leakage checks. "
            f"Review: {leakage_report}"
        )

    manifest_path = project_root / "data/manifests/dataset_manifest.json"
    quality_path = project_root / "data/manifests/fuseg2021_quality_report.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    quality_path.write_text(json.dumps(quality_report, indent=2) + "\n", encoding="utf-8")

    print(
        "FUSeg2021 manifest written: "
        f"train={manifest['split_summary']['train_samples']}, "
        f"val={manifest['split_summary']['val_samples']}, "
        f"test_images={manifest['split_summary']['test_samples']}, "
        f"excluded={manifest['split_summary']['excluded_samples']}"
    )
    print(f"Quality report: {quality_path}")


if __name__ == "__main__":
    main()
