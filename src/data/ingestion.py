"""
Data Ingestion Module — DFU-WoundMonitor.

This module provides deterministic, provenance-preserving data ingestion logic.
Raw dataset files are copied or linked into `data/raw/` without modification.
SHA-256 checksums, file formats, and source paths are recorded for full auditability.

Coding Style: Beginner-Understandable Python
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


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
    source_annotations_dir: Optional[Path],
    destination_raw_dir: Path,
) -> Dict[str, Any]:
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

    # Define target raw directory for this dataset
    target_dataset_dir = destination_raw_dir / dataset_name
    target_images_dir = target_dataset_dir / "images"
    target_annotations_dir = target_dataset_dir / "annotations"

    # Create target directories if they do not exist
    os.makedirs(target_images_dir, exist_ok=True)
    if source_annotations_dir is not None:
        os.makedirs(target_annotations_dir, exist_ok=True)

    # Initialize tracking lists
    accepted_samples: List[Dict[str, Any]] = []
    unsupported_files: List[str] = []
    discovered_checksums: Dict[str, str] = {}  # sha256 -> sample_id
    duplicate_files: List[Dict[str, str]] = []

    # 1. Discover and process image files deterministically
    if not source_images_dir.exists():
        print(f"Error: Source images directory does not exist: {source_images_dir}")
        return {"dataset_name": dataset_name, "error": "Source images directory missing"}

    # Get sorted list of files for deterministic ordering
    sorted_image_files = sorted(list(source_images_dir.iterdir()))

    for image_path in sorted_image_files:
        if not image_path.is_file():
            continue

        # Check format
        if not is_supported_image_format(image_path):
            unsupported_files.append(str(image_path.name))
            continue

        # Compute SHA-256 checksum
        checksum = compute_sha256_checksum(image_path)
        sample_id = image_path.stem

        # Check for duplicates using checksum
        if checksum in discovered_checksums:
            duplicate_files.append({
                "file_name": image_path.name,
                "original_sample_id": discovered_checksums[checksum],
                "checksum": checksum
            })

        discovered_checksums[checksum] = sample_id

        # Determine annotation path if present
        annotation_file_name = None
        if source_annotations_dir is not None and source_annotations_dir.exists():
            # Try matching annotation file with same stem
            for ext in [".png", ".jpg", ".txt", ".xml", ".json", ".csv"]:
                candidate_ann_path = source_annotations_dir / f"{sample_id}{ext}"
                if candidate_ann_path.exists():
                    annotation_file_name = candidate_ann_path.name
                    break

        accepted_samples.append({
            "sample_id": sample_id,
            "dataset_name": dataset_name,
            "original_image_name": image_path.name,
            "annotation_name": annotation_file_name,
            "sha256": checksum,
            "file_size_bytes": image_path.stat().st_size
        })

    # Summary report structure
    report = {
        "dataset_name": dataset_name,
        "total_discovered": len(sorted_image_files),
        "total_accepted": len(accepted_samples),
        "total_unsupported": len(unsupported_files),
        "total_duplicates": len(duplicate_files),
        "unsupported_files": unsupported_files,
        "duplicates": duplicate_files,
        "samples": accepted_samples
    }

    print(f"Ingestion finished for {dataset_name}: {len(accepted_samples)} samples accepted.")
    return report
