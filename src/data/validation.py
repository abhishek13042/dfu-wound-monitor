"""
Data Quality and Annotation Validation Module — DFU-WoundMonitor.

This module validates image file integrity, image dimensions, bounding box geometry,
segmentation mask dimensions/values, and metadata correctness.

All errors are categorized into explicit issue taxonomies without altering raw files.

Coding Style: Beginner-Understandable Python
"""

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def validate_image_file(image_path: Path) -> tuple[bool, dict[str, Any] | None, str | None]:
    """
    Attempt to open and decode an image file using PIL.

    Inputs:
        image_path: Path object pointing to the image file.

    Outputs:
        Tuple containing:
        - is_valid (bool): True if image can be decoded, False otherwise.
        - metadata (dict or None): Dictionary with width, height, channels, format.
        - error_category (str or None): Issue category string if invalid.

    Assumptions:
        Image file is accessible on disk.
    """
    if not image_path.exists():
        return False, None, "missing_file"

    try:
        # Open image with PIL (lazy loading)
        with Image.open(image_path) as img:
            # Force decoding to detect corrupted file headers or truncation
            img.verify()

        # Re-open after verify() because PIL requires re-opening to read properties
        with Image.open(image_path) as img:
            width, height = img.size
            mode = img.mode

            # Determine channel count from PIL image mode
            channel_mapping = {
                "L": 1,        # Grayscale
                "RGB": 3,      # Standard 3-channel RGB
                "RGBA": 4,     # 4-channel with Alpha
                "CMYK": 4
            }
            channels = channel_mapping.get(mode, len(img.getbands()))

            metadata = {
                "width": width,
                "height": height,
                "channels": channels,
                "format": img.format,
                "mode": mode,
                "file_size_bytes": image_path.stat().st_size
            }

            # Check for unusual or zero dimensions
            if width <= 0 or height <= 0:
                return False, metadata, "unusual_dimensions"

            return True, metadata, None

    except Exception:
        # File could not be parsed or decoded by PIL
        return False, None, "unreadable_image"


def validate_bounding_box(
    bbox: tuple[float, float, float, float],
    image_width: int,
    image_height: int
) -> tuple[bool, str | None]:
    """
    Validate bounding box geometry [x_min, y_min, x_max, y_max].

    Inputs:
        bbox: Tuple of 4 floats (x_min, y_min, x_max, y_max).
        image_width: Width of the parent image in pixels.
        image_height: Height of the parent image in pixels.

    Outputs:
        Tuple of (is_valid: bool, issue_category: str or None).

    Validation Rules:
    1. x_min must be strictly less than x_max (positive width).
    2. y_min must be strictly less than y_max (positive height).
    3. Box coordinates must lie within image boundaries [0, 0, image_width, image_height].
    """
    x_min, y_min, x_max, y_max = bbox

    # 1. Check positive width and height
    box_width = x_max - x_min
    box_height = y_max - y_min

    if box_width <= 0 or box_height <= 0:
        return False, "invalid_bbox"

    # 2. Check boundary limits
    if x_min < 0 or y_min < 0 or x_max > image_width or y_max > image_height:
        return False, "out_of_bounds_bbox"

    return True, None


def validate_segmentation_mask(
    mask_path: Path,
    expected_width: int,
    expected_height: int
) -> tuple[bool, dict[str, Any] | None, str | None]:
    """
    Validate binary or multi-class segmentation mask file.

    Inputs:
        mask_path: Path object pointing to mask file (usually PNG).
        expected_width: Width of corresponding RGB image.
        expected_height: Height of corresponding RGB image.

    Outputs:
        Tuple of (is_valid: bool, mask_stats: dict or None, issue_category: str or None).

    Validation Rules:
    1. Mask file must decode cleanly as grayscale / 2D array.
    2. Mask dimensions must match parent image dimensions exactly.
    3. Binary masks should contain valid pixel values (e.g. 0 for background, >0 for wound).
    """
    if not mask_path.exists():
        return False, None, "missing_annotation"

    try:
        # Load mask image into NumPy array
        with Image.open(mask_path) as mask_img:
            mask_array = np.array(mask_img)

        # 1. Check shape dimensions (Height x Width)
        if mask_array.ndim == 3:
            # Take first channel if 3D array (RGB mask)
            mask_array = mask_array[:, :, 0]

        mask_height, mask_width = mask_array.shape

        if mask_width != expected_width or mask_height != expected_height:
            return False, {
                "mask_width": mask_width,
                "mask_height": mask_height,
                "expected_width": expected_width,
                "expected_height": expected_height
            }, "invalid_mask"

        # 2. Compute non-zero pixel statistics
        unique_values = np.unique(mask_array).tolist()
        foreground_pixels = int(np.count_nonzero(mask_array))
        total_pixels = int(mask_array.size)
        wound_ratio = float(foreground_pixels / total_pixels) if total_pixels > 0 else 0.0

        mask_stats = {
            "mask_width": mask_width,
            "mask_height": mask_height,
            "unique_values": unique_values,
            "foreground_pixels": foreground_pixels,
            "total_pixels": total_pixels,
            "wound_area_ratio": round(wound_ratio, 6)
        }

        # Check if mask is completely empty when an annotation was expected
        # Note: Empty mask is recorded as an issue category if present
        if foreground_pixels == 0:
            return True, mask_stats, "empty_mask"

        return True, mask_stats, None

    except Exception:
        return False, None, "invalid_mask"


def run_dataset_quality_validation(
    ingestion_report: dict[str, Any],
    raw_images_dir: Path,
    raw_annotations_dir: Path | None,
    require_annotation: bool = False,
) -> dict[str, Any]:
    """
    Perform full data quality and annotation validation across all ingested samples.

    Inputs:
        ingestion_report: Output dictionary from P01-S02 ingestion.
        raw_images_dir: Path to directory containing raw image files.
        raw_annotations_dir: Optional path to raw annotations directory.
        require_annotation: If True, samples without a paired annotation are
            invalid. This is required for the Phase 02 wound-segmentation task.

    Outputs:
        Dictionary report containing validation statistics and issue categorization.
    """
    samples = ingestion_report.get("samples", [])
    dataset_name = ingestion_report.get("dataset_name", "Unknown")

    print(f"Running quality validation for dataset: {dataset_name} ({len(samples)} samples)...")

    valid_samples_count = 0
    issue_summary: dict[str, int] = {
        "unreadable_image": 0,
        "malformed_annotation": 0,
        "invalid_bbox": 0,
        "out_of_bounds_bbox": 0,
        "invalid_mask": 0,
        "empty_mask": 0,
        "missing_annotation": 0,
        "missing_file": 0,
        "unusual_dimensions": 0,
        "duplicate": 0
    }

    sample_results: list[dict[str, Any]] = []

    for sample in samples:
        sample_id = sample["sample_id"]
        image_name = sample["original_image_name"]
        annotation_name = sample.get("annotation_name")

        image_path = raw_images_dir / image_name

        # 1. Validate Image
        img_valid, img_meta, img_issue = validate_image_file(image_path)

        if not img_valid or img_meta is None:
            if img_issue:
                issue_summary[img_issue] = issue_summary.get(img_issue, 0) + 1
            sample_results.append({
                "sample_id": sample_id,
                "dataset_name": dataset_name,
                "is_valid": False,
                "issue_category": img_issue,
                "image_metadata": None,
                "mask_metadata": None
            })
            continue

        width = img_meta["width"]
        height = img_meta["height"]

        # 2. Validate Mask/Annotation if present
        mask_meta = None
        sample_issue = None

        if annotation_name is None and require_annotation:
            sample_issue = "missing_annotation"
            issue_summary[sample_issue] += 1
        elif annotation_name is not None and raw_annotations_dir is not None:
            mask_path = raw_annotations_dir / annotation_name
            mask_valid, mask_meta, mask_issue = validate_segmentation_mask(mask_path, width, height)

            if not mask_valid or mask_issue is not None:
                if mask_issue:
                    issue_summary[mask_issue] = issue_summary.get(mask_issue, 0) + 1
                    sample_issue = mask_issue

        is_sample_clean = (img_valid and (sample_issue is None))
        if is_sample_clean:
            valid_samples_count += 1

        sample_results.append({
            "sample_id": sample_id,
            "dataset_name": dataset_name,
            "is_valid": is_sample_clean,
            "issue_category": sample_issue,
            "image_metadata": img_meta,
            "mask_metadata": mask_meta
        })

    validation_report = {
        "dataset_name": dataset_name,
        "total_samples": len(samples),
        "valid_samples": valid_samples_count,
        "invalid_samples": len(samples) - valid_samples_count,
        "issue_summary": issue_summary,
        "sample_results": sample_results
    }

    print(f"Validation complete for {dataset_name}: {valid_samples_count}/{len(samples)} valid.")
    return validation_report
