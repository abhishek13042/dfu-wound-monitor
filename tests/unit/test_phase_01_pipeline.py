"""
Unit test suite verifying Phase 01 data pipeline implementation.

Tests P01-S01 through P01-S06 logic for correctness, determinism, and data safety.
"""

import json
from pathlib import Path
import unittest
import numpy as np
from PIL import Image

from src.data.ingestion import compute_sha256_checksum, is_supported_image_format
from src.data.validation import validate_bounding_box, validate_segmentation_mask
from src.data.schema import map_source_label_to_canonical, create_canonical_sample_metadata
from src.data.splitting import generate_deterministic_splits, verify_split_leakage
from src.data.eda import compute_dataset_statistics


class TestPhase01Pipeline(unittest.TestCase):
    """
    TestCase class for Phase 01 data foundation modules.
    """

    def setUp(self) -> None:
        """Set up test paths and temporary resources."""
        self.project_root = Path(__file__).parent.parent.parent
        self.registry_path = self.project_root / "data" / "external" / "dataset_registry.json"

    def test_p01_s01_dataset_registry_integrity(self) -> None:
        """P01-S01: Verify dataset registry exists and contains required dataset entries."""
        self.assertTrue(self.registry_path.exists(), "Dataset registry JSON file is missing.")

        with open(self.registry_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        datasets = data.get("datasets", [])
        dataset_names = {d["dataset_name"] for d in datasets}

        expected_names = {"DFUC2020", "DFUC2021", "DFUC2022", "DFUTissueSegNet", "FUSeg2021"}
        self.assertTrue(expected_names.issubset(dataset_names), f"Missing dataset entries: {expected_names - dataset_names}")

    def test_p01_s02_checksum_determinism(self) -> None:
        """P01-S02: Verify SHA-256 checksum calculation determinism."""
        test_file = Path(__file__)
        hash_1 = compute_sha256_checksum(test_file)
        hash_2 = compute_sha256_checksum(test_file)

        self.assertEqual(hash_1, hash_2, "SHA-256 hash must be deterministic across calls.")
        self.assertEqual(len(hash_1), 64, "SHA-256 hex string must be exactly 64 characters.")

    def test_p01_s03_bounding_box_validation(self) -> None:
        """P01-S03: Verify bounding box geometry validation rules."""
        # Valid box inside 512x512 image
        is_valid, issue = validate_bounding_box((100, 100, 300, 300), 512, 512)
        self.assertTrue(is_valid)
        self.assertIsNone(issue)

        # Invalid geometry (negative width: x_min > x_max)
        is_valid, issue = validate_bounding_box((300, 100, 100, 300), 512, 512)
        self.assertFalse(is_valid)
        self.assertEqual(issue, "invalid_bbox")

        # Out-of-bounds box (x_max > image_width)
        is_valid, issue = validate_bounding_box((100, 100, 600, 300), 512, 512)
        self.assertFalse(is_valid)
        self.assertEqual(issue, "out_of_bounds_bbox")

    def test_p01_s04_label_harmonization(self) -> None:
        """P01-S04: Verify source -> canonical label mapping."""
        canonical, status, notes = map_source_label_to_canonical("DFUC2022", "wound")
        self.assertEqual(canonical, "wound_tissue")
        self.assertEqual(status, "VERIFIED")

        canonical_tissue, status_t, _ = map_source_label_to_canonical("DFUTissueSegNet", "fibrin")
        self.assertEqual(canonical_tissue, "tissue_fibrin")
        self.assertEqual(status_t, "VERIFIED")
        _, status_slough, _ = map_source_label_to_canonical("DFUTissueSegNet", "slough")
        self.assertNotEqual(status_slough, "VERIFIED")

    def test_p01_s05_patient_aware_splitting_and_leakage(self) -> None:
        """P01-S05: Verify patient-level splitting and leakage detection."""
        # Create synthetic patient samples
        samples = [
            {"sample_id": "S1", "patient_id": "P01", "checksum_sha256": "hash_a"},
            {"sample_id": "S2", "patient_id": "P01", "checksum_sha256": "hash_b"},
            {"sample_id": "S3", "patient_id": "P02", "checksum_sha256": "hash_c"},
            {"sample_id": "S4", "patient_id": "P02", "checksum_sha256": "hash_d"},
            {"sample_id": "S5", "patient_id": "P03", "checksum_sha256": "hash_e"},
            {"sample_id": "S6", "patient_id": "P04", "checksum_sha256": "hash_f"},
        ]

        manifest_records, summary = generate_deterministic_splits(
            sample_records=samples,
            train_ratio=0.50,
            val_ratio=0.25,
            test_ratio=0.25,
            random_seed=42
        )

        self.assertTrue(summary["patient_level_isolation_achieved"])

        # Run leakage check
        leakage = verify_split_leakage(manifest_records)
        self.assertTrue(leakage["leakage_test_passed"], "Patient-level splitting should have zero leakage.")
        self.assertFalse(leakage["patient_leakage_detected"])

    def test_p01_s06_eda_statistics_computation(self) -> None:
        """P01-S06: Verify EDA statistical summary calculations."""
        records = [
            {"width": 512, "height": 512, "split": "train", "canonical_label": "wound_tissue"},
            {"width": 512, "height": 512, "split": "val", "canonical_label": "wound_tissue"},
        ]

        stats = compute_dataset_statistics(records)
        self.assertEqual(stats["total_samples"], 2)
        self.assertEqual(stats["width_stats"]["mean"], 512.0)
        self.assertEqual(stats["aspect_ratio_stats"]["mean"], 1.0)

    def test_p01_s05_exam_level_grouping_when_patient_ids_absent(self) -> None:
        """Repeated images from one verified examination stay together."""
        samples = [
            {"sample_id": "E1_A", "exam_id": "EXAM01", "checksum_sha256": "h1"},
            {"sample_id": "E1_B", "exam_id": "EXAM01", "checksum_sha256": "h2"},
            {"sample_id": "E2_A", "exam_id": "EXAM02", "checksum_sha256": "h3"},
            {"sample_id": "E3_A", "exam_id": "EXAM03", "checksum_sha256": "h4"},
        ]
        records, summary = generate_deterministic_splits(
            sample_records=samples,
            train_ratio=0.5,
            val_ratio=0.25,
            test_ratio=0.25,
            random_seed=42,
        )

        split_by_id = {record["sample_id"]: record["split"] for record in records}
        self.assertEqual(split_by_id["E1_A"], split_by_id["E1_B"])
        self.assertEqual(summary["split_mode"], "EXAM_LEVEL")
        self.assertTrue(summary["exam_level_isolation_achieved"])


if __name__ == "__main__":
    unittest.main()
