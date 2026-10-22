"""
Phase 01 Data Pipeline Orchestrator — DFU-WoundMonitor.

This script executes the complete, deterministic Phase 01 pipeline across all specifications:
- P01-S01: Dataset Source Verification & Registry Load
- P01-S02: Ingestion & Checksum Generation
- P01-S03: Data Quality & Annotation Validation
- P01-S04: Canonical Schema & Label Harmonization
- P01-S05: Deterministic Patient-Aware Splitting & Manifest Generation
- P01-S06: EDA & Visualization Grid Rendering

Coding Style: Beginner-Understandable Python
"""

import json
import os
import argparse
import sys
from pathlib import Path
from typing import Optional, Tuple

# Make direct execution from the repository root resolve the project package.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import our modular pipeline functions
from src.data.ingestion import ingest_dataset_directory
from src.data.validation import run_dataset_quality_validation
from src.data.schema import create_canonical_sample_metadata
from src.data.splitting import generate_deterministic_splits, verify_split_leakage
from src.data.eda import compute_dataset_statistics, create_visualization_grid
from PIL import Image
import numpy as np


def create_synthetic_demo_dataset(base_dir: Path) -> Tuple[Path, Path]:
    """
    Create a clean, reproducible synthetic demo dataset to verify the Phase 01 pipeline.

    Generates 20 synthetic foot images and corresponding binary segmentation masks.
    """
    source_img_dir = base_dir / "demo_source" / "images"
    source_ann_dir = base_dir / "demo_source" / "annotations"

    os.makedirs(source_img_dir, exist_ok=True)
    os.makedirs(source_ann_dir, exist_ok=True)

    print(f"Generating synthetic benchmark samples at: {source_img_dir}")

    for i in range(1, 21):
        sample_id = f"DFUC22_{i:04d}"
        img_path = source_img_dir / f"{sample_id}.png"
        ann_path = source_ann_dir / f"{sample_id}.png"

        if not img_path.exists():
            # Create 512x512 RGB synthetic image
            img_data = np.zeros((512, 512, 3), dtype=np.uint8) + 180  # Skin tone background
            # Add synthetic wound region
            img_data[150:350, 150:350, 0] = 220  # Red wound center
            img_data[150:350, 150:350, 1] = 50
            img_data[150:350, 150:350, 2] = 50

            Image.fromarray(img_data).save(img_path)

            # Create 512x512 binary segmentation mask (0 background, 255 wound)
            mask_data = np.zeros((512, 512), dtype=np.uint8)
            mask_data[150:350, 150:350] = 255

            Image.fromarray(mask_data).save(ann_path)

    return source_img_dir, source_ann_dir


def run_phase_01_pipeline(
    dataset_root: Optional[Path] = None,
    images_dir: Optional[Path] = None,
    annotations_dir: Optional[Path] = None,
    dataset_version: str = "unknown",
    use_synthetic_demo: bool = False,
):
    """Execute the end-to-end Phase 01 pipeline for a verified local dataset.

    A real dataset source must be supplied explicitly. The synthetic fixture is
    available only with ``--demo`` and is marked as a smoke-test source in the
    generated manifest. There is no download or silent fallback behavior.
    """
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data"
    raw_dir = data_dir / "raw"
    manifests_dir = data_dir / "manifests"
    reports_dir = project_root / "reports"
    outputs_dir = project_root / "outputs" / "visualizations"

    os.makedirs(manifests_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(outputs_dir, exist_ok=True)

    print("==================================================")
    print("      DFU-WoundMonitor — Phase 01 Pipeline        ")
    print("==================================================")

    # 1. P01-S01: Verify Registry
    registry_path = data_dir / "external" / "dataset_registry.json"
    with open(registry_path, "r", encoding="utf-8") as f:
        registry = json.load(f)
    print(f"[P01-S01] Registry loaded: {len(registry['datasets'])} verified dataset entries.")

    # 2. P01-S02: Select an explicit source for primary segmentation.
    if use_synthetic_demo:
        demo_img_dir, demo_ann_dir = create_synthetic_demo_dataset(data_dir / "interim")
        source_img_dir = demo_img_dir
        source_ann_dir = demo_ann_dir
        source_type = "synthetic_demo"
        resolved_dataset_version = "synthetic-demo-1"
    else:
        if images_dir is None and dataset_root is not None:
            images_dir = dataset_root / "images"
        if annotations_dir is None and dataset_root is not None:
            annotations_dir = dataset_root / "annotations"

        if images_dir is None or annotations_dir is None:
            raise RuntimeError(
                "REAL DATA BASELINE BLOCKED: provide --dataset-root PATH with "
                "images/ and annotations/ directories, or provide both "
                "--images-dir and --annotations-dir. Use --demo only for the "
                "historical synthetic smoke fixture."
            )
        if not images_dir.is_dir() or not annotations_dir.is_dir():
            raise FileNotFoundError(
                "REAL DATA BASELINE BLOCKED: expected local DFUC2022 directories "
                f"were not found: images={images_dir}, annotations={annotations_dir}."
            )
        source_img_dir = images_dir
        source_ann_dir = annotations_dir
        source_type = "real"
        resolved_dataset_version = dataset_version

    ingestion_report = ingest_dataset_directory(
        dataset_name="DFUC2022",
        source_images_dir=source_img_dir,
        source_annotations_dir=source_ann_dir,
        destination_raw_dir=raw_dir
    )

    with open(reports_dir / "ingestion_report.json", "w", encoding="utf-8") as f:
        json.dump(ingestion_report, f, indent=2)
    print("[P01-S02] Ingestion report saved to reports/ingestion_report.json.")

    # 3. P01-S03: Data Quality Validation
    validation_report = run_dataset_quality_validation(
        ingestion_report=ingestion_report,
        raw_images_dir=raw_dir / "DFUC2022" / "images",
        raw_annotations_dir=raw_dir / "DFUC2022" / "annotations",
        require_annotation=True,
    )

    with open(manifests_dir / "quality_validation_report.json", "w", encoding="utf-8") as f:
        json.dump(validation_report, f, indent=2)
    print("[P01-S03] Validation report saved to data/manifests/quality_validation_report.json.")

    # 4. P01-S04: Schema & Label Harmonization
    canonical_samples = []
    exclusion_records = []
    ingestion_samples_by_id = {
        sample["sample_id"]: sample for sample in ingestion_report.get("samples", [])
    }
    duplicate_sample_ids = {
        duplicate["file_name"].rsplit(".", 1)[0]
        for duplicate in ingestion_report.get("duplicates", [])
    }
    for s_result in validation_report["sample_results"]:
        sample_id = s_result["sample_id"]
        ingest_sample = ingestion_samples_by_id[sample_id]

        img_meta = s_result.get("image_metadata") or {"width": 512, "height": 512, "channels": 3}

        if not s_result["is_valid"]:
            exclusion_records.append(
                {
                    "sample_id": sample_id,
                    "dataset": "DFUC2022",
                    "reason": s_result.get("issue_category") or "validation_failed",
                    "validation_status": "INVALID",
                }
            )
            continue

        if sample_id in duplicate_sample_ids:
            exclusion_records.append(
                {
                    "sample_id": sample_id,
                    "dataset": "DFUC2022",
                    "reason": "duplicate_image_checksum",
                    "validation_status": "QUARANTINED",
                }
            )
            continue

        canonical_obj = create_canonical_sample_metadata(
            dataset_name="DFUC2022",
            dataset_version=resolved_dataset_version,
            source_sample_id=sample_id,
            image_path=ingest_sample["raw_image_path"],
            annotation_path=ingest_sample["raw_annotation_path"],
            checksum_sha256=ingest_sample["sha256"],
            width=img_meta["width"],
            height=img_meta["height"],
            channels=img_meta["channels"],
            annotation_type="wound_segmentation",
            patient_id=None,  # Unknown for DFUC2022 public release
            exam_id=None,
            original_label="wound",
            validation_status="VALID",
            annotation_checksum_sha256=ingest_sample.get("annotation_sha256"),
        )
        canonical_samples.append(canonical_obj.to_dict())

    if not canonical_samples:
        raise RuntimeError(
            "Phase 01 produced no usable DFUC2022 segmentation samples. "
            "Review reports/ingestion_report.json and "
            "data/manifests/quality_validation_report.json."
        )

    # 5. P01-S05: Patient-Aware / Deterministic Splitting
    manifest_records, split_summary = generate_deterministic_splits(
        sample_records=canonical_samples,
        train_ratio=0.70,
        val_ratio=0.15,
        test_ratio=0.15,
        random_seed=42
    )

    leakage_report = verify_split_leakage(manifest_records)
    split_summary["leakage_analysis"] = leakage_report

    manifest_document = {
            "manifest_version": "1.1.0",
            "dataset_name": "DFUC2022",
            "dataset_version": resolved_dataset_version,
            "dataset_source_type": source_type,
            "source_images_dir": str(source_img_dir),
            "source_annotations_dir": str(source_ann_dir),
            "split_summary": split_summary,
            "exclusions": exclusion_records,
            "samples": manifest_records,
        }
    with open(manifests_dir / "dataset_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest_document, f, indent=2)

    print(f"[P01-S05] Manifest saved. Split summary: Train={split_summary['train_samples']}, Val={split_summary['val_samples']}, Test={split_summary['test_samples']}.")
    print(f"[P01-S05] Leakage verification passed: {leakage_report['leakage_test_passed']}.")

    # 6. P01-S06: EDA & Visualization
    eda_stats = compute_dataset_statistics(manifest_records)
    with open(reports_dir / "eda_summary.json", "w", encoding="utf-8") as f:
        json.dump(eda_stats, f, indent=2)

    # Render EDA Visualization Grid
    viz_images = [Path(s["image_path"]) for s in manifest_records[:8]]
    viz_masks = [Path(s["annotation_path"]) if s["annotation_path"] else None for s in manifest_records[:8]]
    viz_labels = [f"{s.get('source_sample_id') or s.get('sample_id')} ({s['split']})" for s in manifest_records[:8]]

    grid_path = create_visualization_grid(
        image_paths=viz_images,
        mask_paths=viz_masks,
        labels=viz_labels,
        output_grid_path=outputs_dir / "phase_01_annotation_grid.png",
        cols=4
    )

    print(f"[P01-S06] EDA visualization grid rendered to: {grid_path}")
    print("\n==================================================")
    if not leakage_report["leakage_test_passed"]:
        raise RuntimeError(
            "TRAINING STOPPED: split leakage validation failed. "
            "The manifest was written for audit, but Phase 02 training is blocked "
            "until the split is corrected."
        )

    print("        PHASE 01 PIPELINE EXECUTION PASSED        ")
    print("==================================================")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the Phase 01 DFUC2022 ingestion and manifest pipeline."
    )
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument(
        "--dataset-root",
        type=Path,
        help="Local verified DFUC2022 root containing images/ and annotations/.",
    )
    source_group.add_argument(
        "--demo",
        action="store_true",
        help="Use the historical synthetic fixture for smoke testing only.",
    )
    parser.add_argument("--images-dir", type=Path, default=None)
    parser.add_argument("--annotations-dir", type=Path, default=None)
    parser.add_argument("--dataset-version", default="unknown")
    args = parser.parse_args()

    run_phase_01_pipeline(
        dataset_root=args.dataset_root,
        images_dir=args.images_dir,
        annotations_dir=args.annotations_dir,
        dataset_version=args.dataset_version,
        use_synthetic_demo=args.demo,
    )
