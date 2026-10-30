"""
Patient-Aware Splitting and Manifest Generation Module — DFU-WoundMonitor.

Primary Rule: When reliable patient IDs exist: PATIENT -> split (not IMAGE -> split).
When patient metadata is absent, fallback image-level splitting is documented without
claiming patient-level isolation.

Coding Style: Beginner-Understandable Python
"""

import json
import random
from pathlib import Path
from typing import Any


def get_sample_identifier(sample: dict[str, Any]) -> str:
    """Extract sample identifier supporting both 'sample_id' and 'source_sample_id' keys."""
    return sample.get("sample_id") or sample.get("source_sample_id") or "unknown_sample"


def generate_deterministic_splits(
    sample_records: list[dict[str, Any]],
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    random_seed: int = 42
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Partition dataset samples into deterministic Train, Validation, and Test splits.

    If patient_id metadata is present:
        Performs Group-K-Fold partitioning on patient_id so all samples from a patient
        stay in the same split.
    If patient_id metadata is absent:
        Performs deterministic sample-level partitioning with explicit limitation notes.

    Inputs:
        sample_records: List of sample dictionaries (canonical metadata).
        train_ratio: Proportion of data for training (default 0.70).
        val_ratio: Proportion of data for validation (default 0.15).
        test_ratio: Proportion of data for testing (default 0.15).
        random_seed: Fixed random seed for reproducibility (default 42).

    Outputs:
        Tuple containing:
        - manifest_records: List of sample records with added 'split' field.
        - split_summary: Metadata dictionary summarizing counts, ratios, seed, and grouping mode.
    """
    # Verify split ratios sum to 1.0
    total_ratio = train_ratio + val_ratio + test_ratio
    if abs(total_ratio - 1.0) > 1e-5:
        raise ValueError(f"Split ratios must sum to 1.0, got {total_ratio}")

    # Set deterministic random seed
    random.seed(random_seed)

    # Check whether verified grouping metadata is available. Patient grouping
    # has priority; examination grouping is the next-safe fallback.
    has_patient_ids = any(
        s.get("patient_id") is not None and s.get("patient_id") != "UNKNOWN"
        for s in sample_records
    )
    has_exam_ids = any(
        s.get("exam_id") is not None and s.get("exam_id") != "UNKNOWN"
        for s in sample_records
    )

    grouping_field = "patient_id" if has_patient_ids else ("exam_id" if has_exam_ids else None)
    if grouping_field == "patient_id":
        split_mode = "PATIENT_LEVEL"
    elif grouping_field == "exam_id":
        split_mode = "EXAM_LEVEL"
    else:
        split_mode = "IMAGE_LEVEL_FALLBACK"

    manifest_records: list[dict[str, Any]] = []

    if grouping_field is not None:
        print(
            f"Executing {split_mode} splitting across {len(sample_records)} samples..."
        )

        # Group samples by the strongest verified grouping identifier.
        grouped_samples: dict[str, list[dict[str, Any]]] = {}
        for sample in sample_records:
            grouping_id = sample.get(grouping_field, "UNKNOWN")
            if grouping_id not in grouped_samples:
                grouped_samples[grouping_id] = []
            grouped_samples[grouping_id].append(sample)

        # Shuffle unique group identifiers deterministically.
        unique_group_ids = sorted(list(grouped_samples.keys()))
        random.shuffle(unique_group_ids)

        # Compute group count thresholds.
        num_groups = len(unique_group_ids)
        num_train_groups = int(num_groups * train_ratio)
        num_val_groups = int(num_groups * val_ratio)

        train_group_ids = set(unique_group_ids[:num_train_groups])
        val_group_ids = set(
            unique_group_ids[num_train_groups : num_train_groups + num_val_groups]
        )

        # Assign samples based on the group's split.
        for grouping_id, group_samples in grouped_samples.items():
            if grouping_id in train_group_ids:
                assigned_split = "train"
            elif grouping_id in val_group_ids:
                assigned_split = "val"
            else:
                assigned_split = "test"

            for s in group_samples:
                record = dict(s)
                record["split"] = assigned_split
                manifest_records.append(record)

    else:
        print(f"Executing IMAGE-LEVEL FALLBACK splitting across {len(sample_records)} samples...")

        # Sort samples for deterministic shuffle
        sorted_samples = sorted(sample_records, key=get_sample_identifier)
        shuffled_samples = [dict(s) for s in sorted_samples]
        random.shuffle(shuffled_samples)

        num_total = len(shuffled_samples)
        num_train = int(num_total * train_ratio)
        num_val = int(num_total * val_ratio)

        for index, sample in enumerate(shuffled_samples):
            if index < num_train:
                sample["split"] = "train"
            elif index < num_train + num_val:
                sample["split"] = "val"
            else:
                sample["split"] = "test"
            manifest_records.append(sample)

    # Calculate summary counts per split
    train_count = sum(1 for s in manifest_records if s["split"] == "train")
    val_count = sum(1 for s in manifest_records if s["split"] == "val")
    test_count = sum(1 for s in manifest_records if s["split"] == "test")

    split_summary = {
        "split_mode": split_mode,
        "random_seed": random_seed,
        "train_ratio": train_ratio,
        "val_ratio": val_ratio,
        "test_ratio": test_ratio,
        "total_samples": len(manifest_records),
        "train_samples": train_count,
        "val_samples": val_count,
        "test_samples": test_count,
        "patient_level_isolation_achieved": has_patient_ids,
        "exam_level_isolation_achieved": has_exam_ids,
        "grouping_field": grouping_field,
        "limitation_note": (
            "Patient IDs present; patient-level isolation enforced."
            if has_patient_ids
            else (
                "Exam IDs present but patient IDs absent; examination-level isolation enforced."
                if has_exam_ids
                else "Patient and exam IDs absent in public release; split is image-level fallback. Cannot claim patient-level isolation."
            )
        )
    }

    return manifest_records, split_summary


def verify_split_leakage(manifest_records: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Run automated checks to verify zero leakage across train, val, and test splits.

    Checks:
    1. Image checksum overlap across splits.
    2. Annotation checksum overlap across splits.
    3. Patient ID overlap across splits.
    4. Examination ID overlap across splits.
    5. Exact path duplication across splits.

    Inputs:
        manifest_records: List of sample dictionaries containing 'split' assignments.

    Outputs:
        Dictionary report containing leakage test status and overlap details.
    """
    split_checksums: dict[str, set[str]] = {"train": set(), "val": set(), "test": set()}
    split_sample_ids: dict[str, set[str]] = {"train": set(), "val": set(), "test": set()}
    split_annotation_checksums: dict[str, set[str]] = {
        "train": set(),
        "val": set(),
        "test": set(),
    }
    annotation_checksum_records: dict[str, list[dict[str, Any]]] = {}
    split_patients: dict[str, set[str]] = {"train": set(), "val": set(), "test": set()}
    split_exams: dict[str, set[str]] = {"train": set(), "val": set(), "test": set()}
    split_image_paths: dict[str, set[str]] = {"train": set(), "val": set(), "test": set()}
    split_annotation_paths: dict[str, set[str]] = {
        "train": set(),
        "val": set(),
        "test": set(),
    }

    for sample in manifest_records:
        split = sample["split"]
        if split not in split_checksums:
            # Excluded/quarantined samples are not part of a model split.
            continue
        split_sample_ids[split].add(get_sample_identifier(sample))
        checksum = sample.get("checksum_sha256")
        annotation_checksum = sample.get("annotation_checksum_sha256")
        patient_id = sample.get("patient_id")
        exam_id = sample.get("exam_id")
        image_path = sample.get("image_path")
        annotation_path = sample.get("annotation_path")

        if checksum:
            split_checksums[split].add(checksum)
        if annotation_checksum:
            split_annotation_checksums[split].add(annotation_checksum)
            annotation_checksum_records.setdefault(annotation_checksum, []).append(sample)
        if patient_id and patient_id != "UNKNOWN":
            split_patients[split].add(patient_id)
        if exam_id and exam_id != "UNKNOWN":
            split_exams[split].add(exam_id)
        if image_path:
            split_image_paths[split].add(str(Path(image_path).as_posix()).lower())
        if annotation_path:
            split_annotation_paths[split].add(str(Path(annotation_path).as_posix()).lower())

    # 1. Compute Checksum Overlaps
    sample_id_train_val = split_sample_ids["train"].intersection(split_sample_ids["val"])
    sample_id_train_test = split_sample_ids["train"].intersection(split_sample_ids["test"])
    sample_id_val_test = split_sample_ids["val"].intersection(split_sample_ids["test"])

    # 2. Compute Checksum Overlaps
    checksum_train_val = split_checksums["train"].intersection(split_checksums["val"])
    checksum_train_test = split_checksums["train"].intersection(split_checksums["test"])
    checksum_val_test = split_checksums["val"].intersection(split_checksums["test"])

    # 3. Compute Patient Overlaps
    patient_train_val = split_patients["train"].intersection(split_patients["val"])
    patient_train_test = split_patients["train"].intersection(split_patients["test"])
    patient_val_test = split_patients["val"].intersection(split_patients["test"])

    # 4. Compute annotation checksum overlaps
    annotation_train_val = split_annotation_checksums["train"].intersection(
        split_annotation_checksums["val"]
    )
    annotation_train_test = split_annotation_checksums["train"].intersection(
        split_annotation_checksums["test"]
    )
    annotation_val_test = split_annotation_checksums["val"].intersection(
        split_annotation_checksums["test"]
    )

    # 5. Compute examination overlaps
    exam_train_val = split_exams["train"].intersection(split_exams["val"])
    exam_train_test = split_exams["train"].intersection(split_exams["test"])
    exam_val_test = split_exams["val"].intersection(split_exams["test"])

    # 6. Compute exact path overlaps. This catches a manifest that references
    # the same file through different identifiers even when checksums are absent.
    image_path_train_val = split_image_paths["train"].intersection(split_image_paths["val"])
    image_path_train_test = split_image_paths["train"].intersection(split_image_paths["test"])
    image_path_val_test = split_image_paths["val"].intersection(split_image_paths["test"])
    annotation_path_train_val = split_annotation_paths["train"].intersection(
        split_annotation_paths["val"]
    )
    annotation_path_train_test = split_annotation_paths["train"].intersection(
        split_annotation_paths["test"]
    )
    annotation_path_val_test = split_annotation_paths["val"].intersection(
        split_annotation_paths["test"]
    )

    has_checksum_leakage = bool(checksum_train_val or checksum_train_test or checksum_val_test)
    has_sample_id_leakage = bool(sample_id_train_val or sample_id_train_test or sample_id_val_test)
    # An exact repeated empty mask is a valid and common segmentation target;
    # its checksum is not a patient/sample identifier and must not by itself
    # block a split. Non-empty annotation checksum overlap remains a hard
    # warning. Fixtures without the explicit foreground count retain the
    # conservative historical behavior and are treated as overlap.
    repeated_empty_mask_checksums: set[str] = set()
    for annotation_checksum, records in annotation_checksum_records.items():
        splits = {record.get("split") for record in records}
        foreground_counts = [record.get("quality", {}).get("mask_foreground_pixels") for record in records]
        if len(splits) > 1 and foreground_counts and all(count == 0 for count in foreground_counts):
            repeated_empty_mask_checksums.add(annotation_checksum)

    annotation_checksum_leakage_pairs = {
        "train_vs_val": annotation_train_val - repeated_empty_mask_checksums,
        "train_vs_test": annotation_train_test - repeated_empty_mask_checksums,
        "val_vs_test": annotation_val_test - repeated_empty_mask_checksums,
    }
    has_annotation_checksum_leakage = any(annotation_checksum_leakage_pairs.values())
    has_patient_leakage = bool(patient_train_val or patient_train_test or patient_val_test)
    has_exam_leakage = bool(exam_train_val or exam_train_test or exam_val_test)
    has_path_leakage = bool(
        image_path_train_val
        or image_path_train_test
        or image_path_val_test
        or annotation_path_train_val
        or annotation_path_train_test
        or annotation_path_val_test
    )

    leakage_passed = not (
        has_checksum_leakage
        or has_sample_id_leakage
        or has_annotation_checksum_leakage
        or has_patient_leakage
        or has_exam_leakage
        or has_path_leakage
    )

    return {
        "leakage_test_passed": leakage_passed,
        "checksum_leakage_detected": has_checksum_leakage,
        "sample_id_leakage_detected": has_sample_id_leakage,
        "annotation_checksum_leakage_detected": has_annotation_checksum_leakage,
        "patient_leakage_detected": has_patient_leakage,
        "exam_leakage_detected": has_exam_leakage,
        "exact_path_duplication_detected": has_path_leakage,
        "checksum_overlaps": {
            "train_vs_val": len(checksum_train_val),
            "train_vs_test": len(checksum_train_test),
            "val_vs_test": len(checksum_val_test)
        },
        "sample_id_overlaps": {
            "train_vs_val": len(sample_id_train_val),
            "train_vs_test": len(sample_id_train_test),
            "val_vs_test": len(sample_id_val_test),
        },
        "annotation_checksum_overlaps": {
            "train_vs_val": len(annotation_train_val),
            "train_vs_test": len(annotation_train_test),
            "val_vs_test": len(annotation_val_test),
        },
        "repeated_empty_mask_checksums_allowed": len(repeated_empty_mask_checksums),
        "annotation_checksum_leakage_overlaps": {
            pair: len(checksums) for pair, checksums in annotation_checksum_leakage_pairs.items()
        },
        "patient_overlaps": {
            "train_vs_val": len(patient_train_val),
            "train_vs_test": len(patient_train_test),
            "val_vs_test": len(patient_val_test)
        },
        "exam_overlaps": {
            "train_vs_val": len(exam_train_val),
            "train_vs_test": len(exam_train_test),
            "val_vs_test": len(exam_val_test),
        },
        "exact_path_overlaps": {
            "image_train_vs_val": len(image_path_train_val),
            "image_train_vs_test": len(image_path_train_test),
            "image_val_vs_test": len(image_path_val_test),
            "annotation_train_vs_val": len(annotation_path_train_val),
            "annotation_train_vs_test": len(annotation_path_train_test),
            "annotation_val_vs_test": len(annotation_path_val_test),
        }
    }


def validate_manifest_for_training(
    manifest_path: str,
    require_real_data: bool = True,
) -> dict[str, Any]:
    """Validate hard training gates before any model data loader is created.

    SPEC-02-01 training is allowed only from an explicitly declared real
    FUSeg2021 manifest whose split leakage checks pass. Historical synthetic
    manifests remain available for unit tests and smoke testing, but cannot be
    used for the real baseline run.

    Returns the parsed manifest data when all gates pass.
    Raises ``RuntimeError`` with an actionable message when a gate fails.
    """
    manifest_file = Path(manifest_path)
    if not manifest_file.exists():
        raise RuntimeError(
            f"REAL DATA BASELINE BLOCKED: manifest not found at '{manifest_path}'. "
            "Build a verified local real-data manifest before training."
        )

    with manifest_file.open("r", encoding="utf-8") as manifest_handle:
        manifest_data = json.load(manifest_handle)

    source_type = manifest_data.get("dataset_source_type")
    if require_real_data and source_type != "real":
        raise RuntimeError(
            "REAL DATA BASELINE BLOCKED: the manifest must declare "
            "dataset_source_type='real'. Synthetic demo manifests are not valid "
            "for final training or evaluation."
        )

    if require_real_data and manifest_data.get("dataset_name") != "FUSeg2021":
        raise RuntimeError(
            "REAL DATA BASELINE BLOCKED: SPEC-02-01 requires dataset_name='FUSeg2021'. "
            f"Found '{manifest_data.get('dataset_name')}'."
        )

    samples = manifest_data.get("samples", [])
    if not isinstance(samples, list) or not samples:
        raise RuntimeError("REAL DATA BASELINE BLOCKED: manifest contains no samples.")

    split_summary = manifest_data.get("split_summary", {})
    leakage_analysis = split_summary.get("leakage_analysis", {})
    if leakage_analysis.get("leakage_test_passed") is not True:
        raise RuntimeError(
            "TRAINING STOPPED: manifest leakage validation did not pass. "
            "Fix image/annotation checksum, patient/exam, and exact-path overlaps "
            "before training."
        )

    # Do not trust a cached report alone.  Recompute the gate from the records
    # that can enter the model split so a stale or hand-edited manifest cannot
    # silently bypass leakage checks.
    leakage_records = [
        sample
        for sample in samples
        if sample.get("validation_status") in (None, "VALID")
    ]
    recomputed_leakage = verify_split_leakage(leakage_records)
    if recomputed_leakage["leakage_test_passed"] is not True:
        raise RuntimeError(
            "TRAINING STOPPED: recomputed manifest leakage validation did not pass. "
            f"Details: {recomputed_leakage}"
        )

    required_counts = ("train_samples", "val_samples", "test_samples")
    missing_counts = [key for key in required_counts if not split_summary.get(key)]
    if missing_counts:
        raise RuntimeError(
            "REAL DATA BASELINE BLOCKED: manifest must contain non-empty train, "
            f"validation, and test splits; missing/empty fields: {missing_counts}."
        )

    # When the manifest carries the full canonical record fields, verify that
    # the supervised splits actually contain usable annotations.  Small unit
    # fixtures may omit those optional fields and are intentionally left to the
    # dataset constructor for path-level validation.
    records_with_status = [sample for sample in samples if "validation_status" in sample]
    if records_with_status:
        annotated_counts = {
            split: sum(
                sample.get("split") == split
                and sample.get("validation_status") == "VALID"
                and sample.get("annotation_type") == "wound_segmentation"
                for sample in records_with_status
            )
            for split in ("train", "val")
        }
        empty_annotated_splits = [split for split, count in annotated_counts.items() if count == 0]
        if empty_annotated_splits:
            raise RuntimeError(
                "REAL DATA BASELINE BLOCKED: no valid wound-segmentation annotations in "
                f"split(s): {empty_annotated_splits}."
            )
        if manifest_data.get("split_summary", {}).get("usable_test_samples", 0) != 0:
            raise RuntimeError(
                "REAL DATA BASELINE BLOCKED: SPEC-02-01 must not use public FUSeg2021 "
                "test images as labeled samples."
            )

    split_ids: dict[str, set[str]] = {"train": set(), "val": set(), "test": set()}
    for sample in samples:
        split = sample.get("split")
        sample_id = get_sample_identifier(sample)
        if split in split_ids:
            if sample_id in split_ids[split]:
                raise RuntimeError(
                    f"TRAINING STOPPED: duplicate sample identifier '{sample_id}' "
                    f"inside the {split} split."
                )
            split_ids[split].add(sample_id)

    return manifest_data
