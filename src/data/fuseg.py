"""FUSeg2021 data-contract inspection and manifest construction.

The public FUSeg2021 release already defines train, validation, and test
directories.  This module preserves those official assignments instead of
creating a new split.  It never changes files in the raw source tree.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

OFFICIAL_SPLITS = ("train", "validation", "test")
SPLIT_NAMES = {"train": "train", "validation": "val", "test": "test"}
SPLIT_PRIORITY = {"train": 0, "validation": 1, "test": 2}
SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
EXPECTED_MASK_VALUES = {0, 255}


def compute_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Return the SHA-256 digest of ``path`` without loading it all at once."""

    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        while chunk := file_handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_path(path: Path | None, project_root: Path) -> str | None:
    """Represent a local path relative to the project for portable manifests."""

    if path is None:
        return None
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError as error:
        raise ValueError(
            f"FUSeg path '{path}' must be inside project root '{project_root}'."
        ) from error


def _image_files(directory: Path) -> list[Path]:
    """List supported image files in deterministic order."""

    if not directory.is_dir():
        return []
    return sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
        ),
        key=lambda path: path.name.lower(),
    )


def _decode_image(path: Path) -> tuple[bool, dict[str, Any], str | None]:
    """Decode an image and return metadata plus an explicit failure reason."""

    metadata: dict[str, Any] = {"path": str(path)}
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            image.load()
            metadata.update(
                {
                    "width": image.width,
                    "height": image.height,
                    "mode": image.mode,
                    "format": image.format,
                    "channels": len(image.getbands()),
                }
            )
        if metadata["width"] <= 0 or metadata["height"] <= 0:
            return False, metadata, "unusual_dimensions"
        return True, metadata, None
    except Exception as error:  # PIL raises several format-specific exceptions.
        metadata["decode_error"] = str(error)
        return False, metadata, "unreadable_image"


def _inspect_mask(
    path: Path,
    expected_width: int,
    expected_height: int,
) -> tuple[bool, dict[str, Any], str | None]:
    """Validate a FUSeg binary mask without silently normalizing source bytes."""

    metadata: dict[str, Any] = {"path": str(path)}
    try:
        with Image.open(path) as mask_image:
            mask_image.load()
            array = np.asarray(mask_image)
            if array.ndim == 3:
                # FUSeg masks are expected to be grayscale.  Do not discard
                # disagreement between channels; record it as invalid below.
                channels_equal = bool(np.all(array == array[:, :, :1]))
                if not channels_equal:
                    return False, {"mode": mask_image.mode}, "multichannel_mask"
                array = array[:, :, 0]

            unique_values = sorted(int(value) for value in np.unique(array))
            metadata.update(
                {
                    "width": int(mask_image.width),
                    "height": int(mask_image.height),
                    "mode": mask_image.mode,
                    "format": mask_image.format,
                    "unique_values": unique_values,
                    "foreground_pixels": int(np.count_nonzero(array)),
                    "total_pixels": int(array.size),
                    "empty_mask": bool(not np.any(array)),
                    "checksum_sha256": compute_sha256(path),
                }
            )

        if metadata["width"] != expected_width or metadata["height"] != expected_height:
            return False, metadata, "mask_dimension_mismatch"
        if not set(metadata["unique_values"]).issubset(EXPECTED_MASK_VALUES):
            return False, metadata, "unexpected_mask_values"
        return True, metadata, None
    except Exception as error:
        metadata["decode_error"] = str(error)
        return False, metadata, "unreadable_mask"


def _duplicate_groups(records: Iterable[dict[str, Any]], key: str) -> dict[str, list[str]]:
    """Group sample IDs by a checksum field, retaining only duplicate groups."""

    grouped: dict[str, list[str]] = defaultdict(list)
    for record in records:
        checksum = record.get(key)
        if checksum:
            grouped[checksum].append(record["source_sample_id"])
    return {checksum: sample_ids for checksum, sample_ids in grouped.items() if len(sample_ids) > 1}


def build_fuseg_manifest(
    source_root: Path,
    project_root: Path,
    dataset_version: str,
    source_commit: str,
    source_content_digest: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Inspect FUSeg2021 and build a manifest plus a machine-readable quality report.

    The first valid occurrence of an exact duplicate image is retained using
    official split priority (train, validation, test), then sample ID.  Later
    occurrences are quarantined in the manifest.  This removes the seven
    train/validation image collisions and duplicate training supervision from
    the model-development splits without deleting or modifying raw files.
    """

    source_root = source_root.resolve()
    project_root = project_root.resolve()
    if not source_root.is_dir():
        raise FileNotFoundError(f"FUSeg source root not found: {source_root}")

    records: list[dict[str, Any]] = []
    split_quality: dict[str, Any] = {}
    for official_split in OFFICIAL_SPLITS:
        split_root = source_root / official_split
        image_root = split_root / "images"
        label_root = split_root / "labels"
        image_paths = _image_files(image_root)
        label_paths = _image_files(label_root)
        label_by_stem = {path.stem: path for path in label_paths}
        image_stems = {path.stem for path in image_paths}

        split_report: dict[str, Any] = {
            "official_split": official_split,
            "image_count": len(image_paths),
            "label_count": len(label_paths),
            "missing_labels": sorted(image_stems - set(label_by_stem))
            if official_split != "test"
            else [],
            "orphan_labels": sorted(set(label_by_stem) - image_stems),
            "decode_failures": [],
            "mask_issues": [],
            "dimensions": {},
            "mask_values": {},
            "empty_mask_count": 0,
        }

        for image_path in image_paths:
            sample_id = image_path.stem
            image_valid, image_metadata, image_issue = _decode_image(image_path)
            image_checksum = compute_sha256(image_path) if image_valid else None
            mask_path = label_by_stem.get(sample_id)
            mask_valid = False
            mask_metadata: dict[str, Any] = {}
            mask_issue: str | None = None
            if official_split != "test" and mask_path is None:
                mask_issue = "missing_annotation"
            elif mask_path is not None and image_valid:
                mask_valid, mask_metadata, mask_issue = _inspect_mask(
                    mask_path,
                    expected_width=image_metadata["width"],
                    expected_height=image_metadata["height"],
                )

            if image_issue:
                split_report["decode_failures"].append(
                    {"sample_id": sample_id, "issue": image_issue, "metadata": image_metadata}
                )
            if mask_issue:
                split_report["mask_issues"].append(
                    {"sample_id": sample_id, "issue": mask_issue, "metadata": mask_metadata}
                )
            if image_valid:
                dimension_key = f"{image_metadata['width']}x{image_metadata['height']}"
                split_report["dimensions"][dimension_key] = (
                    split_report["dimensions"].get(dimension_key, 0) + 1
                )
            if mask_valid:
                value_key = ",".join(str(value) for value in mask_metadata["unique_values"])
                split_report["mask_values"][value_key] = (
                    split_report["mask_values"].get(value_key, 0) + 1
                )
                split_report["empty_mask_count"] += int(mask_metadata["empty_mask"])

            records.append(
                {
                    "dataset_name": "FUSeg2021",
                    "dataset_version": dataset_version,
                    "source_sample_id": sample_id,
                    "official_split": official_split,
                    "split": SPLIT_NAMES[official_split],
                    "image_path": _relative_path(image_path, project_root),
                    "annotation_path": _relative_path(mask_path, project_root),
                    "checksum_sha256": image_checksum,
                    "annotation_checksum_sha256": mask_metadata.get("checksum_sha256"),
                    "width": image_metadata.get("width"),
                    "height": image_metadata.get("height"),
                    "channels": image_metadata.get("channels"),
                    "annotation_type": (
                        "wound_segmentation" if official_split != "test" else "unlabeled_test"
                    ),
                    "patient_id": None,
                    "exam_id": None,
                    "original_label": "wound" if official_split != "test" else "unlabeled",
                    "canonical_label": "wound_tissue" if official_split != "test" else "unlabeled",
                    "metadata_status": "VERIFIED",
                    "validation_status": "VALID" if image_valid else "INVALID",
                    "issue_category": image_issue or mask_issue,
                    "quality": {
                        "image_mode": image_metadata.get("mode"),
                        "mask_unique_values": mask_metadata.get("unique_values"),
                        "mask_foreground_pixels": mask_metadata.get("foreground_pixels"),
                        "mask_empty": mask_metadata.get("empty_mask"),
                    },
                }
            )
        split_quality[official_split] = split_report

    records_by_image_checksum: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record.get("checksum_sha256"):
            records_by_image_checksum[record["checksum_sha256"]].append(record)

    duplicate_image_groups = {
        checksum: [record["source_sample_id"] for record in group]
        for checksum, group in records_by_image_checksum.items()
        if len(group) > 1
    }
    duplicate_image_groups_by_split = {
        official_split: {
            checksum: [record["source_sample_id"] for record in group if record["official_split"] == official_split]
            for checksum, group in records_by_image_checksum.items()
            if sum(record["official_split"] == official_split for record in group) > 1
        }
        for official_split in OFFICIAL_SPLITS
    }
    cross_split_duplicate_groups = {
        checksum: [
            f"{record['official_split']}/{record['source_sample_id']}" for record in group
        ]
        for checksum, group in records_by_image_checksum.items()
        if len({record["official_split"] for record in group}) > 1
    }

    # Keep one deterministic representative of each exact duplicate image.
    # Prefer a record with a usable supervised mask.  Otherwise an invalid
    # train copy could quarantine a valid validation copy and silently remove
    # an otherwise trainable sample from the manifest.
    for group in records_by_image_checksum.values():
        ordered_group = sorted(
            group,
            key=lambda record: (
                0
                if (
                    record["validation_status"] == "VALID"
                    and record["annotation_type"] == "wound_segmentation"
                    and record.get("issue_category") is None
                )
                else 1,
                SPLIT_PRIORITY[record["official_split"]],
                record["source_sample_id"],
            ),
        )
        keeper = ordered_group[0]
        for duplicate in ordered_group[1:]:
            duplicate["validation_status"] = "QUARANTINED"
            if duplicate["official_split"] != keeper["official_split"]:
                duplicate["issue_category"] = "cross_split_duplicate_image"
            else:
                duplicate["issue_category"] = "duplicate_image_within_split"
            duplicate["duplicate_of"] = keeper["source_sample_id"]

    # Invalid annotations are excluded even when the image itself decodes.
    for record in records:
        if record["official_split"] != "test" and record.get("issue_category") is None:
            # A valid image with a missing/unreadable/unexpected mask was not
            # assigned an issue above only when the image itself failed.
            if not record.get("annotation_path"):
                record["validation_status"] = "INVALID"
                record["issue_category"] = "missing_annotation"
        if record["official_split"] == "test" and record["validation_status"] == "VALID":
            # Public test images are valid inputs but have no usable labels.
            record["annotation_path"] = None
            record["annotation_checksum_sha256"] = None

    # The issue on a valid mask is stored in the record by the inspection loop;
    # ensure it is represented as INVALID after duplicate handling.
    for record in records:
        if (
            record["official_split"] != "test"
            and record.get("issue_category") in {
                "missing_annotation",
                "unreadable_mask",
                "mask_dimension_mismatch",
                "unexpected_mask_values",
                "multichannel_mask",
            }
        ):
            record["validation_status"] = "INVALID"

    duplicate_mask_groups = _duplicate_groups(records, "annotation_checksum_sha256")
    usable_records = [
        record
        for record in records
        if record["validation_status"] == "VALID"
        and record["annotation_type"] == "wound_segmentation"
    ]
    exclusions = [
        {
            "sample_id": record["source_sample_id"],
            "official_split": record["official_split"],
            "split": record["split"],
            "reason": record.get("issue_category"),
            "validation_status": record["validation_status"],
            "duplicate_of": record.get("duplicate_of"),
        }
        for record in records
        if record["validation_status"] != "VALID"
    ]

    manifest = {
        "manifest_version": "2.0.0",
        "dataset_name": "FUSeg2021",
        "dataset_version": dataset_version,
        "dataset_source_type": "real",
        "source_root": _relative_path(source_root, project_root),
        "official_source": "https://fusc.grand-challenge.org/FUSeg-2021/",
        "source_repository": "https://github.com/uwm-bigdata/wound-segmentation",
        "source_commit": source_commit,
        "source_content_digest": source_content_digest,
        "split_policy": "official FUSeg2021 train/validation/test directories; no re-split",
        "patient_id_policy": "No patient or examination identifiers are available; none inferred.",
        "split_summary": {
            "split_mode": "OFFICIAL_SOURCE_SPLIT",
            "patient_level_isolation_achieved": False,
            "exam_level_isolation_achieved": False,
            "limitation_note": (
                "Official FUSeg2021 split assignments were preserved. The public release "
                "does not provide usable patient or examination identifiers, so patient-level "
                "isolation cannot be claimed. Exact duplicate image collisions were quarantined."
            ),
            "official_counts": {
                "train": sum(record["official_split"] == "train" for record in records),
                "validation": sum(record["official_split"] == "validation" for record in records),
                "test": sum(record["official_split"] == "test" for record in records),
            },
            "train_samples": sum(record["split"] == "train" for record in usable_records),
            "val_samples": sum(record["split"] == "val" for record in usable_records),
            "test_samples": sum(record["split"] == "test" for record in records),
            "usable_test_samples": 0,
            "excluded_samples": len(exclusions),
        },
        "exclusions": exclusions,
        "samples": records,
    }

    quality_report = {
        "dataset_name": "FUSeg2021",
        "dataset_version": dataset_version,
        "source_root": _relative_path(source_root, project_root),
        "source_commit": source_commit,
        "source_content_digest": source_content_digest,
        "official_split_information": {
            "train": "train/images + train/labels",
            "validation": "validation/images + validation/labels",
            "test": "test/images only; no public ground-truth labels",
        },
        "patient_identifiers": {
            "available": False,
            "policy": "No identifiers were inferred from filenames or directory structure.",
        },
        "splits": split_quality,
        "duplicate_images": {
            "all_duplicate_groups": duplicate_image_groups,
            "within_split": duplicate_image_groups_by_split,
            "cross_split": cross_split_duplicate_groups,
        },
        "duplicate_masks": duplicate_mask_groups,
        "duplicate_mask_policy": (
            "Repeated empty masks are reported but are not treated as cross-split image leakage; "
            "a mask checksum is not a patient or sample identifier."
        ),
        "usable_counts": {
            "train": sum(record["split"] == "train" for record in usable_records),
            "validation": sum(record["split"] == "val" for record in usable_records),
            "test_images_without_ground_truth": sum(
                record["split"] == "test" for record in records
            ),
        },
        "exclusion_counts_by_reason": {
            reason: sum(item["reason"] == reason for item in exclusions)
            for reason in sorted({item["reason"] for item in exclusions})
        },
        "mask_contract": {
            "expected_values": [0, 255],
            "conversion": "threshold at 128 after nearest-neighbor resize to binary {0, 1}",
            "empty_masks_are_valid": True,
        },
    }
    return manifest, quality_report
