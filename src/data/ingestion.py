"""
Data Ingestion Module — DFU-WoundMonitor.

This module provides deterministic, provenance-preserving data ingestion logic.
Raw dataset files are copied or linked into `data/raw/` without modification.
SHA-256 checksums, file formats, and source paths are recorded for full auditability.

Coding Style: Beginner-Understandable Python
"""

import hashlib
import shutil
from pathlib import Path
from typing import Any


def compute_sha256_checksum(file_path: Path, buffer_size: int = 65536) -> str:
    """
    Calculate the SHA-256 hash checksum of a file.

    Inputs:
        file_path: Path object pointing to the target file.
        buffer_size: Number of bytes to read per block (default 64KB).

    Outputs:
        Hexadecimal string representation of the SHA-256 checksum.

    Assumptions:
        File exists and is readable in binary mode.
    """
    # Create SHA-256 hash object
    hasher = hashlib.sha256()

    # Open file in binary read mode ('rb') to handle both text and binary files safely
    with open(file_path, "rb") as input_file:
        while True:
            # Read chunk from file
            file_chunk = input_file.read(buffer_size)
            if not file_chunk:
                # End of file reached
                break
            # Update hash with chunk
            hasher.update(file_chunk)

    return hasher.hexdigest()


def is_supported_image_format(file_path: Path) -> bool:
    """
    Check if a file has a supported image extension.

    Inputs:
        file_path: Target file path.

    Outputs:
        True if extension is supported (.jpg, .jpeg, .png, .bmp), False otherwise.
    """
    supported_extensions = {".jpg", ".jpeg", ".png", ".bmp"}
    return file_path.suffix.lower() in supported_extensions


def is_supported_annotation_format(file_path: Path) -> bool:
    """
    Check if a file has a supported annotation extension.

    Inputs:
        file_path: Target file path.

    Outputs:
        True if extension is supported (.png, .jpg, .txt, .xml, .json, .csv), False otherwise.
    """
    supported_extensions = {".png", ".jpg", ".jpeg", ".txt", ".xml", ".json", ".csv"}
    return file_path.suffix.lower() in supported_extensions


def ingest_dataset_directory(
    dataset_name: str,
    source_images_dir: Path,
    source_annotations_dir: Path | None,
    destination_raw_dir: Path,
) -> dict[str, Any]:
    """
    Ingest images and annotations into the data/raw/ storage layer.

    This function:
    1. Scans the source directory deterministically (sorted order).
    2. Verifies file formats and computes SHA-256 checksums.
    3. Copies/links files into data/raw/<dataset_name>/ without modifying them.
    4. Generates an ingestion manifest record.

    Inputs:
        dataset_name: Name identifier for the dataset (e.g., 'DFUC2022').
        source_images_dir: Path to directory containing source images.
        source_annotations_dir: Optional Path to directory containing source annotations.
        destination_raw_dir: Path to project raw storage directory (e.g., 'data/raw/').

    Outputs:
        Dictionary report summarizing ingestion results (counts, checksums, errors).
    """
    print(f"Starting deterministic ingestion for dataset: {dataset_name}")

    if not source_images_dir.exists() or not source_images_dir.is_dir():
        raise FileNotFoundError(
            f"Source images directory does not exist: {source_images_dir}. "
            "Provide a verified local dataset directory; no download fallback is used."
        )

    # Raw files are copied without changing their bytes. If the source already is
    # the configured raw directory, the copy step is safely skipped.
    target_dataset_dir = destination_raw_dir / dataset_name
    target_images_dir = target_dataset_dir / "images"
    target_annotations_dir = target_dataset_dir / "annotations"
    target_images_dir.mkdir(parents=True, exist_ok=True)
    if source_annotations_dir is not None:
        target_annotations_dir.mkdir(parents=True, exist_ok=True)

    accepted_samples: list[dict[str, Any]] = []
    unsupported_files: list[str] = []
    errors: list[dict[str, str]] = []
    discovered_checksums: dict[str, str] = {}
    duplicate_files: list[dict[str, str]] = []

    sorted_image_files = sorted(source_images_dir.iterdir(), key=lambda path: path.name)

    for image_path in sorted_image_files:
        if not image_path.is_file():
            continue

        if not is_supported_image_format(image_path):
            unsupported_files.append(str(image_path.name))
            continue

        checksum = compute_sha256_checksum(image_path)
        sample_id = image_path.stem

        if checksum in discovered_checksums:
            duplicate_files.append(
                {
                    "file_name": image_path.name,
                    "original_sample_id": discovered_checksums[checksum],
                    "checksum": checksum,
                }
            )
        else:
            discovered_checksums[checksum] = sample_id

        annotation_path: Path | None = None
        if source_annotations_dir is not None and source_annotations_dir.exists():
            for extension in [".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"]:
                candidate_path = source_annotations_dir / f"{sample_id}{extension}"
                if candidate_path.exists():
                    annotation_path = candidate_path
                    break

        target_image_path = target_images_dir / image_path.name
        target_annotation_path = (
            target_annotations_dir / annotation_path.name if annotation_path else None
        )

        try:
            if image_path.resolve() != target_image_path.resolve():
                shutil.copy2(image_path, target_image_path)
            if annotation_path is not None and target_annotation_path is not None:
                if annotation_path.resolve() != target_annotation_path.resolve():
                    shutil.copy2(annotation_path, target_annotation_path)
        except OSError as copy_error:
            errors.append(
                {
                    "sample_id": sample_id,
                    "error": f"raw_copy_failed: {copy_error}",
                }
            )
            continue

        annotation_checksum = (
            compute_sha256_checksum(annotation_path) if annotation_path is not None else None
        )
        accepted_samples.append(
            {
                "sample_id": sample_id,
                "dataset_name": dataset_name,
                "original_image_name": image_path.name,
                "annotation_name": annotation_path.name if annotation_path else None,
                "source_image_path": str(image_path),
                "source_annotation_path": str(annotation_path) if annotation_path else None,
                "raw_image_path": str(target_image_path),
                "raw_annotation_path": (
                    str(target_annotation_path) if target_annotation_path else None
                ),
                "sha256": checksum,
                "annotation_sha256": annotation_checksum,
                "file_size_bytes": image_path.stat().st_size,
            }
        )

    report = {
        "dataset_name": dataset_name,
        "source_images_dir": str(source_images_dir),
        "source_annotations_dir": str(source_annotations_dir) if source_annotations_dir else None,
        "destination_raw_dir": str(target_dataset_dir),
        "total_discovered": len(sorted_image_files),
        "total_accepted": len(accepted_samples),
        "total_unsupported": len(unsupported_files),
        "total_duplicates": len(duplicate_files),
        "unsupported_files": unsupported_files,
        "duplicates": duplicate_files,
        "errors": errors,
        "samples": accepted_samples,
    }

    print(
        f"Ingestion finished for {dataset_name}: "
        f"{len(accepted_samples)} samples accepted, "
        f"{len(duplicate_files)} duplicate image checksums."
    )
    return report
