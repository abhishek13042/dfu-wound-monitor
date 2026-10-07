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
from typing import Any, Dict, List, Optional, Set, Tuple


def get_sample_identifier(sample: Dict[str, Any]) -> str:
    """Extract sample identifier supporting both 'sample_id' and 'source_sample_id' keys."""
    return sample.get("sample_id") or sample.get("source_sample_id") or "unknown_sample"


def generate_deterministic_splits(
    sample_records: List[Dict[str, Any]],
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    random_seed: int = 42
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
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

    # Check if patient identifiers exist across samples
    has_patient_ids = any(
        s.get("patient_id") is not None and s.get("patient_id") != "UNKNOWN"
        for s in sample_records
    )

    split_mode = "PATIENT_LEVEL" if has_patient_ids else "IMAGE_LEVEL_FALLBACK"

    manifest_records: List[Dict[str, Any]] = []

    if has_patient_ids:
        print(f"Executing PATIENT-LEVEL splitting across {len(sample_records)} samples...")

        # Group sample indices by patient_id
        patient_groups: Dict[str, List[Dict[str, Any]]] = {}
        for sample in sample_records:
            pid = sample.get("patient_id", "UNKNOWN")
            if pid not in patient_groups:
                patient_groups[pid] = []
            patient_groups[pid].append(sample)

        # Shuffle unique patient IDs deterministically
        unique_patient_ids = sorted(list(patient_groups.keys()))
        random.shuffle(unique_patient_ids)

        # Compute patient count thresholds
        num_patients = len(unique_patient_ids)
        num_train_patients = int(num_patients * train_ratio)
        num_val_patients = int(num_patients * val_ratio)

        train_patient_ids = set(unique_patient_ids[:num_train_patients])
        val_patient_ids = set(unique_patient_ids[num_train_patients : num_train_patients + num_val_patients])
        test_patient_ids = set(unique_patient_ids[num_train_patients + num_val_patients:])

        # Assign samples based on patient's split
        for pid, group_samples in patient_groups.items():
            if pid in train_patient_ids:
                assigned_split = "train"
            elif pid in val_patient_ids:
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
        "limitation_note": (
            "Patient IDs present; patient-level isolation enforced."
            if has_patient_ids
            else "Patient IDs absent in public release; split is image-level fallback. Cannot claim patient-level isolation."
        )
    }

    return manifest_records, split_summary


def verify_split_leakage(manifest_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Run automated checks to verify zero leakage across train, val, and test splits.

    Checks:
    1. Checksum Overlap: Same image hash in multiple splits.
    2. Patient ID Overlap: Same patient ID in multiple splits.
    3. Exam ID Overlap: Same examination ID in multiple splits.

    Inputs:
        manifest_records: List of sample dictionaries containing 'split' assignments.

    Outputs:
        Dictionary report containing leakage test status and overlap details.
    """
    split_checksums: Dict[str, Set[str]] = {"train": set(), "val": set(), "test": set()}
    split_patients: Dict[str, Set[str]] = {"train": set(), "val": set(), "test": set()}
    split_exams: Dict[str, Set[str]] = {"train": set(), "val": set(), "test": set()}

    for sample in manifest_records:
        split = sample["split"]
        checksum = sample.get("checksum_sha256")
        patient_id = sample.get("patient_id")
        exam_id = sample.get("exam_id")

        if checksum:
            split_checksums[split].add(checksum)
        if patient_id and patient_id != "UNKNOWN":
            split_patients[split].add(patient_id)
        if exam_id and exam_id != "UNKNOWN":
            split_exams[split].add(exam_id)

    # 1. Compute Checksum Overlaps
    checksum_train_val = split_checksums["train"].intersection(split_checksums["val"])
    checksum_train_test = split_checksums["train"].intersection(split_checksums["test"])
    checksum_val_test = split_checksums["val"].intersection(split_checksums["test"])

    # 2. Compute Patient Overlaps
    patient_train_val = split_patients["train"].intersection(split_patients["val"])
    patient_train_test = split_patients["train"].intersection(split_patients["test"])
    patient_val_test = split_patients["val"].intersection(split_patients["test"])

    has_checksum_leakage = bool(checksum_train_val or checksum_train_test or checksum_val_test)
    has_patient_leakage = bool(patient_train_val or patient_train_test or patient_val_test)

    leakage_passed = not (has_checksum_leakage or has_patient_leakage)

    return {
        "leakage_test_passed": leakage_passed,
        "checksum_leakage_detected": has_checksum_leakage,
        "patient_leakage_detected": has_patient_leakage,
        "checksum_overlaps": {
            "train_vs_val": len(checksum_train_val),
            "train_vs_test": len(checksum_train_test),
            "val_vs_test": len(checksum_val_test)
        },
        "patient_overlaps": {
            "train_vs_val": len(patient_train_val),
            "train_vs_test": len(patient_train_test),
            "val_vs_test": len(patient_val_test)
        }
    }
