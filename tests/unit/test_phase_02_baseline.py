"""
Phase 02 Baseline Test Suite — DFU-WoundMonitor.

Tests covering:
    - P02-S02: Dataset interface (loading, shapes, alignment, split isolation)
    - P02-S03: Model (initialization, forward pass, loss, output shape)
    - P02-S05: Metrics (mathematical correctness, edge cases, aggregation)

All tests use controlled synthetic or minimal fixture data.
No real training is performed in this test suite.

Coding Style: Beginner-Understandable Python
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest
import torch

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.segmentation.dataset import (
    WoundSegmentationDataset,
    apply_random_horizontal_flip,
    load_manifest_samples,
    preprocess_image,
    preprocess_mask,
)
from src.segmentation.metrics import (
    aggregate_metrics,
    compute_binary_segmentation_metrics,
)
from src.segmentation.model import (
    BCEDiceLoss,
    LightweightUNet,
    count_model_parameters,
    verify_model_forward_pass,
)

from PIL import Image


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def synthetic_rgb_image() -> Image.Image:
    """Return a 512x512 synthetic RGB image."""
    image_array = np.random.randint(0, 256, (512, 512, 3), dtype=np.uint8)
    return Image.fromarray(image_array, mode="RGB")


@pytest.fixture
def synthetic_binary_mask() -> Image.Image:
    """Return a 512x512 binary mask with 0 and 255 values."""
    mask_array = np.zeros((512, 512), dtype=np.uint8)
    # Add a rectangular wound region
    mask_array[100:300, 150:350] = 255
    return Image.fromarray(mask_array, mode="L")


@pytest.fixture
def temp_manifest_with_samples(tmp_path: Path) -> str:
    """
    Create a minimal manifest JSON and matching synthetic image/mask files
    for testing the dataset loader.
    """
    images_dir = tmp_path / "images"
    annotations_dir = tmp_path / "annotations"
    images_dir.mkdir()
    annotations_dir.mkdir()

    sample_ids = ["SYNTH_001", "SYNTH_002", "SYNTH_003"]
    splits = ["train", "train", "val"]

    # Create synthetic PNG image and mask files
    for sample_id in sample_ids:
        # Create RGB image
        image_array = np.random.randint(0, 256, (512, 512, 3), dtype=np.uint8)
        image_pil = Image.fromarray(image_array, mode="RGB")
        image_pil.save(str(images_dir / f"{sample_id}.png"))

        # Create binary mask (0 or 255)
        mask_array = np.zeros((512, 512), dtype=np.uint8)
        mask_array[100:200, 100:200] = 255
        mask_pil = Image.fromarray(mask_array, mode="L")
        mask_pil.save(str(annotations_dir / f"{sample_id}.png"))

    # Build manifest JSON
    manifest_samples = []
    for sample_id, split in zip(sample_ids, splits):
        manifest_samples.append({
            "dataset_name": "TEST_DATASET",
            "dataset_version": "test.1",
            "source_sample_id": sample_id,
            "image_path": str(images_dir / f"{sample_id}.png"),
            "annotation_path": str(annotations_dir / f"{sample_id}.png"),
            "checksum_sha256": "abc123",
            "width": 512,
            "height": 512,
            "channels": 3,
            "annotation_type": "wound_segmentation",
            "patient_id": None,
            "exam_id": None,
            "original_label": "wound",
            "canonical_label": "wound_tissue",
            "metadata_status": "VERIFIED",
            "validation_status": "VALID",
            "split": split,
        })

    manifest_data = {
        "manifest_version": "1.0.0",
        "dataset_name": "TEST_DATASET",
        "split_summary": {},
        "samples": manifest_samples,
    }

    manifest_path = str(tmp_path / "test_manifest.json")
    with open(manifest_path, "w") as manifest_file:
        json.dump(manifest_data, manifest_file)

    return manifest_path


# ============================================================
# P02-S02 TESTS: Dataset Interface
# ============================================================

class TestLoadManifestSamples:
    """Tests for load_manifest_samples() — REQ-P02-S02-001, REQ-P02-S02-008, REQ-P02-S02-009."""

    def test_loads_correct_split(self, temp_manifest_with_samples: str) -> None:
        """Only samples for the requested split are returned."""
        train_samples = load_manifest_samples(temp_manifest_with_samples, split="train")
        assert len(train_samples) == 2
        for sample in train_samples:
            assert sample["split"] == "train"

    def test_val_split_isolated(self, temp_manifest_with_samples: str) -> None:
        """Val split does not contain train samples."""
        val_samples = load_manifest_samples(temp_manifest_with_samples, split="val")
        assert len(val_samples) == 1
        assert val_samples[0]["split"] == "val"

    def test_invalid_split_raises_error(self, temp_manifest_with_samples: str) -> None:
        """Requesting an invalid split raises ValueError."""
        with pytest.raises(ValueError, match="Invalid split"):
            load_manifest_samples(temp_manifest_with_samples, split="invalid_split")

    def test_missing_manifest_raises_error(self) -> None:
        """Missing manifest raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_manifest_samples("/nonexistent/path/manifest.json", split="train")

    def test_invalid_samples_excluded(self, tmp_path: Path) -> None:
        """Samples with validation_status != 'VALID' are excluded (REQ-P02-S02-008)."""
        manifest_data = {
            "manifest_version": "1.0.0",
            "dataset_name": "TEST",
            "split_summary": {},
            "samples": [
                {
                    "source_sample_id": "GOOD_001",
                    "split": "train",
                    "validation_status": "VALID",
                    "annotation_type": "wound_segmentation",
                    "image_path": str(tmp_path / "image.png"),
                    "annotation_path": str(tmp_path / "mask.png"),
                },
                {
                    "source_sample_id": "BAD_001",
                    "split": "train",
                    "validation_status": "INVALID",
                    "annotation_type": "wound_segmentation",
                    "image_path": "",
                    "annotation_path": "",
                },
            ],
        }
        manifest_path = str(tmp_path / "manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest_data, f)

        train_samples = load_manifest_samples(manifest_path, split="train")
        assert len(train_samples) == 1
        assert train_samples[0]["source_sample_id"] == "GOOD_001"


class TestPreprocessImage:
    """Tests for preprocess_image() — REQ-P02-S02-003, REQ-P02-S02-006."""

    def test_output_shape(self, synthetic_rgb_image: Image.Image) -> None:
        """Output tensor has correct shape (3, H, W)."""
        tensor = preprocess_image(
            image_pil=synthetic_rgb_image,
            target_height=256,
            target_width=256,
            normalize_mean=[0.485, 0.456, 0.406],
            normalize_std=[0.229, 0.224, 0.225],
        )
        assert tensor.shape == (3, 256, 256), f"Expected (3, 256, 256), got {tensor.shape}"

    def test_output_dtype(self, synthetic_rgb_image: Image.Image) -> None:
        """Output tensor is float32."""
        tensor = preprocess_image(
            image_pil=synthetic_rgb_image,
            target_height=256,
            target_width=256,
            normalize_mean=[0.485, 0.456, 0.406],
            normalize_std=[0.229, 0.224, 0.225],
        )
        assert tensor.dtype == torch.float32

    def test_grayscale_converted_to_rgb(self) -> None:
        """Grayscale input is converted to 3-channel output."""
        gray_array = np.zeros((64, 64), dtype=np.uint8)
        gray_image = Image.fromarray(gray_array, mode="L")
        tensor = preprocess_image(
            image_pil=gray_image,
            target_height=64,
            target_width=64,
            normalize_mean=[0.0, 0.0, 0.0],
            normalize_std=[1.0, 1.0, 1.0],
        )
        assert tensor.shape[0] == 3


class TestPreprocessMask:
    """Tests for preprocess_mask() — REQ-P02-S02-003, REQ-P02-S02-006, REQ-P02-S02-007."""

    def test_output_shape(self, synthetic_binary_mask: Image.Image) -> None:
        """Output tensor has shape (1, H, W)."""
        tensor = preprocess_mask(
            mask_pil=synthetic_binary_mask,
            target_height=256,
            target_width=256,
        )
        assert tensor.shape == (1, 256, 256), f"Expected (1, 256, 256), got {tensor.shape}"

    def test_output_is_binary(self, synthetic_binary_mask: Image.Image) -> None:
        """Output tensor contains only {0.0, 1.0} values (REQ-P02-S02-007)."""
        tensor = preprocess_mask(
            mask_pil=synthetic_binary_mask,
            target_height=256,
            target_width=256,
        )
        unique_values = torch.unique(tensor).tolist()
        for value in unique_values:
            assert value in [0.0, 1.0], f"Unexpected mask value: {value}"

    def test_wound_region_preserved(self, synthetic_binary_mask: Image.Image) -> None:
        """Wound region in mask remains positive after preprocessing."""
        tensor = preprocess_mask(
            mask_pil=synthetic_binary_mask,
            target_height=256,
            target_width=256,
        )
        # Wound should still be present (non-zero pixels)
        assert tensor.sum() > 0, "Wound region was lost after preprocessing"


class TestAugmentation:
    """Tests for augmentation alignment — REQ-P02-S02-004, REQ-P02-S02-007."""

    def test_flip_applied_consistently(self) -> None:
        """
        When flip is applied, both image and mask are flipped consistently.
        REQ-P02-S02-007: spatial transforms must be applied to image AND mask.
        """
        # Create asymmetric image and mask to detect flip direction
        image_tensor = torch.zeros(3, 8, 8)
        image_tensor[:, :, 0] = 1.0  # Left column is 1

        mask_tensor = torch.zeros(1, 8, 8)
        mask_tensor[:, :, 0] = 1.0  # Left column is 1

        # Force flip (probability=1.0)
        import random
        random.seed(0)  # Ensure we control the random state

        flipped_image, flipped_mask = apply_random_horizontal_flip(
            image_tensor=image_tensor,
            mask_tensor=mask_tensor,
            flip_probability=1.0,  # Always flip
        )

        # After horizontal flip, left column (0) should now be right column (7)
        assert flipped_image[:, :, -1].sum() > 0, "Image not flipped"
        assert flipped_mask[:, :, -1].sum() > 0, "Mask not flipped"

    def test_no_flip_at_zero_probability(self) -> None:
        """With flip_probability=0, tensors are returned unchanged."""
        image_tensor = torch.rand(3, 16, 16)
        mask_tensor = torch.rand(1, 16, 16)

        result_image, result_mask = apply_random_horizontal_flip(
            image_tensor=image_tensor,
            mask_tensor=mask_tensor,
            flip_probability=0.0,
        )

        assert torch.equal(result_image, image_tensor)
        assert torch.equal(result_mask, mask_tensor)


class TestWoundSegmentationDataset:
    """Integration tests for the Dataset class."""

    def test_dataset_len(self, temp_manifest_with_samples: str) -> None:
        """Dataset __len__ matches manifest sample count for split."""
        samples = load_manifest_samples(temp_manifest_with_samples, split="train")
        dataset = WoundSegmentationDataset(
            samples=samples,
            input_height=64,
            input_width=64,
            normalize_mean=[0.485, 0.456, 0.406],
            normalize_std=[0.229, 0.224, 0.225],
            is_training=False,
        )
        assert len(dataset) == 2

    def test_getitem_returns_correct_shapes(self, temp_manifest_with_samples: str) -> None:
        """Dataset __getitem__ returns (image, mask, sample_id) with correct shapes."""
        samples = load_manifest_samples(temp_manifest_with_samples, split="train")
        dataset = WoundSegmentationDataset(
            samples=samples,
            input_height=64,
            input_width=64,
            normalize_mean=[0.485, 0.456, 0.406],
            normalize_std=[0.229, 0.224, 0.225],
            is_training=False,
        )
        image_tensor, mask_tensor, sample_id = dataset[0]

        assert image_tensor.shape == (3, 64, 64), f"Image shape: {image_tensor.shape}"
        assert mask_tensor.shape == (1, 64, 64), f"Mask shape: {mask_tensor.shape}"
        assert isinstance(sample_id, str)

    def test_train_val_split_isolation(self, temp_manifest_with_samples: str) -> None:
        """Train and val samples are disjoint (REQ-P02-S02-009)."""
        train_samples = load_manifest_samples(temp_manifest_with_samples, split="train")
        val_samples = load_manifest_samples(temp_manifest_with_samples, split="val")

        train_ids = {s["source_sample_id"] for s in train_samples}
        val_ids = {s["source_sample_id"] for s in val_samples}

        overlap = train_ids & val_ids
        assert len(overlap) == 0, f"Train/val overlap detected: {overlap}"


# ============================================================
# P02-S03 TESTS: Model and Loss
# ============================================================

class TestLightweightUNet:
    """Tests for the LightweightUNet model — REQ-P02-S03-001 through REQ-P02-S03-008."""

    def test_forward_pass_output_shape(self) -> None:
        """Model output has shape (B, 1, H, W) — REQ-P02-S03-003."""
        model = LightweightUNet(encoder_channels=[8, 16, 32, 64], num_classes=1)
        model.eval()

        input_tensor = torch.randn(2, 3, 64, 64)
        with torch.no_grad():
            output = model(input_tensor)

        assert output.shape == (2, 1, 64, 64), f"Expected (2, 1, 64, 64), got {output.shape}"

    def test_output_is_finite_logits(self) -> None:
        """Model returns finite raw logits; sigmoid is applied at the loss boundary."""
        model = LightweightUNet(encoder_channels=[8, 16, 32, 64], num_classes=1)
        model.eval()

        input_tensor = torch.randn(1, 3, 64, 64)
        with torch.no_grad():
            output = model(input_tensor)

        assert torch.isfinite(output).all()

    def test_parameter_count_is_positive(self) -> None:
        """Model has positive parameter count — REQ-P02-S03-005."""
        model = LightweightUNet(encoder_channels=[16, 32, 64, 128], num_classes=1)
        param_counts = count_model_parameters(model)

        assert param_counts["total_parameters"] > 0
        assert param_counts["trainable_parameters"] > 0
        assert param_counts["trainable_parameters"] == param_counts["total_parameters"]

    def test_verify_forward_pass_utility(self) -> None:
        """verify_model_forward_pass utility returns success — REQ-P02-S03-006."""
        model = LightweightUNet(encoder_channels=[8, 16, 32, 64], num_classes=1)
        results = verify_model_forward_pass(
            model=model,
            input_height=64,
            input_width=64,
            batch_size=2,
        )
        assert results["forward_pass_success"], f"Forward pass failed: {results}"

    def test_output_spatial_size_matches_input(self) -> None:
        """Output spatial dimensions match input spatial dimensions."""
        model = LightweightUNet(encoder_channels=[8, 16, 32, 64], num_classes=1)
        model.eval()

        for height, width in [(64, 64), (128, 128), (256, 256)]:
            input_tensor = torch.randn(1, 3, height, width)
            with torch.no_grad():
                output = model(input_tensor)
            assert output.shape[2] == height, f"Height mismatch: {output.shape}"
            assert output.shape[3] == width, f"Width mismatch: {output.shape}"


class TestBCEDiceLoss:
    """Tests for the BCEDiceLoss — REQ-P02-S03-004."""

    def test_loss_is_scalar(self) -> None:
        """Loss output is a scalar tensor."""
        loss_fn = BCEDiceLoss()
        predictions = torch.rand(2, 1, 32, 32)
        targets = torch.randint(0, 2, (2, 1, 32, 32)).float()

        loss = loss_fn(predictions, targets)
        assert loss.ndim == 0, f"Expected scalar, got shape: {loss.shape}"

    def test_loss_is_finite(self) -> None:
        """Loss value is always finite (no NaN or Inf)."""
        loss_fn = BCEDiceLoss()
        predictions = torch.rand(2, 1, 32, 32)
        targets = torch.randint(0, 2, (2, 1, 32, 32)).float()

        loss = loss_fn(predictions, targets)
        assert torch.isfinite(loss), f"Non-finite loss: {loss.item()}"

    def test_perfect_prediction_has_low_loss(self) -> None:
        """
        Near-perfect prediction should give near-zero loss when foreground exists.

        NOTE on the all-background edge case:
            When targets are all 0 (no wound), predicting all-zeros (background) gives:
                BCE ≈ 0 (correct)
                Dice = (2*0 + eps)/(0 + 0 + eps) ≈ 1.0 → DiceLoss = 0.0 ... but
                only if sum(predictions) ≈ 0 too.
            With predictions=0.001 and targets=0:
                Dice numerator = 2 * sum(0.001 * 0) = 0
                Dice denominator = sum(0.001) + sum(0) = ~1.024 + 0
                DiceLoss ≈ 1 - 0/1.024 ≈ 1.0 → combined loss ≈ 0.5
            This is expected behaviour: Dice Loss with no foreground in GT
            penalises any positive prediction. When GT is all-background, near-zero
            predictions should give near-zero BCE but high Dice denominator issues.

        For a meaningful low-loss test, use a case with matching foreground.
        """
        loss_fn = BCEDiceLoss()
        # Both targets and predictions have the SAME foreground wound region
        targets = torch.zeros(1, 1, 32, 32)
        targets[:, :, 8:24, 8:24] = 1.0      # wound region in ground truth

        predictions = torch.full((1, 1, 32, 32), -8.0)
        predictions[:, :, 8:24, 8:24] = 8.0  # model predicts same region

        loss = loss_fn(predictions, targets)
        assert loss.item() < 0.2, f"Loss too high for near-perfect foreground prediction: {loss.item()}"

    def test_shape_mismatch_raises_error(self) -> None:
        """Loss function raises error on shape mismatch."""
        loss_fn = BCEDiceLoss()
        predictions = torch.rand(2, 1, 32, 32)
        targets = torch.rand(2, 1, 64, 64)  # Different spatial size

        with pytest.raises(ValueError, match="Shape mismatch"):
            loss_fn(predictions, targets)

    def test_all_zero_mask_no_error(self) -> None:
        """Loss is finite when ground truth has no wound (all-zero mask edge case)."""
        loss_fn = BCEDiceLoss()
        predictions = torch.rand(1, 1, 16, 16)
        targets = torch.zeros(1, 1, 16, 16)  # No wound at all

        loss = loss_fn(predictions, targets)
        assert torch.isfinite(loss), "Loss is not finite for all-zero mask"

    def test_logits_contract_is_stable_for_extreme_values(self) -> None:
        """BCEWithLogits + Dice remains finite for large positive/negative logits."""
        loss_fn = BCEDiceLoss()
        predictions = torch.tensor([[[[1000.0, -1000.0], [-1000.0, 1000.0]]]])
        targets = torch.tensor([[[[1.0, 0.0], [0.0, 1.0]]]])
        loss = loss_fn(predictions, targets)
        assert torch.isfinite(loss)


# ============================================================
# P02-S05 TESTS: Metrics
# ============================================================

class TestBinarySegmentationMetrics:
    """Tests for compute_binary_segmentation_metrics() — REQ-P02-S05-004."""

    def test_perfect_prediction_gives_dice_one(self) -> None:
        """Perfect prediction: Dice = 1.0, IoU = 1.0."""
        ground_truth = np.zeros((32, 32), dtype=np.float32)
        ground_truth[8:24, 8:24] = 1.0  # wound region
        predicted = ground_truth.copy()

        metrics = compute_binary_segmentation_metrics(predicted, ground_truth)

        assert abs(metrics["dice"] - 1.0) < 1e-4, f"Dice should be 1.0, got {metrics['dice']}"
        assert abs(metrics["iou"] - 1.0) < 1e-4, f"IoU should be 1.0, got {metrics['iou']}"

    def test_empty_prediction_and_target_gives_one(self) -> None:
        """Both prediction and target are zero → Dice = 1.0 (edge case convention)."""
        predicted = np.zeros((32, 32), dtype=np.float32)
        ground_truth = np.zeros((32, 32), dtype=np.float32)

        metrics = compute_binary_segmentation_metrics(predicted, ground_truth)

        assert metrics["dice"] == 1.0, f"Empty-empty Dice should be 1.0, got {metrics['dice']}"
        assert metrics["iou"] == 1.0, f"Empty-empty IoU should be 1.0, got {metrics['iou']}"

    def test_no_overlap_gives_low_dice(self) -> None:
        """No overlap between prediction and ground truth → Dice = 0.0."""
        ground_truth = np.zeros((32, 32), dtype=np.float32)
        ground_truth[:16, :] = 1.0   # top half

        predicted = np.zeros((32, 32), dtype=np.float32)
        predicted[16:, :] = 1.0      # bottom half (no overlap)

        metrics = compute_binary_segmentation_metrics(predicted, ground_truth)

        assert metrics["dice"] == 0.0, f"No-overlap Dice should be 0.0, got {metrics['dice']}"

    def test_high_fp_reduces_precision(self) -> None:
        """High false positive rate reduces precision."""
        ground_truth = np.zeros((32, 32), dtype=np.float32)
        ground_truth[14:18, 14:18] = 1.0  # small wound

        predicted = np.ones((32, 32), dtype=np.float32)  # predicts everything as wound

        metrics = compute_binary_segmentation_metrics(predicted, ground_truth)

        # Recall should be 1.0 (all wound pixels found)
        assert abs(metrics["recall"] - 1.0) < 1e-4, f"Recall should be 1.0, got {metrics['recall']}"
        # Precision should be very low (huge false positive region)
        assert metrics["precision"] < 0.1, f"Precision should be low, got {metrics['precision']}"

    def test_high_fn_reduces_recall(self) -> None:
        """High false negative rate reduces recall."""
        ground_truth = np.ones((32, 32), dtype=np.float32)  # all wound
        predicted = np.zeros((32, 32), dtype=np.float32)    # predicts nothing

        metrics = compute_binary_segmentation_metrics(predicted, ground_truth)

        assert metrics["recall"] == 0.0, f"Recall should be 0.0, got {metrics['recall']}"


class TestAggregateMetrics:
    """Tests for aggregate_metrics() — REQ-P02-S05-006."""

    def test_aggregate_is_mean(self) -> None:
        """Aggregate dice is the mean of per-sample dice scores."""
        per_sample_results = [
            {"dice": 0.8, "iou": 0.7, "precision": 0.9, "recall": 0.75},
            {"dice": 0.4, "iou": 0.3, "precision": 0.5, "recall": 0.45},
        ]
        aggregate = aggregate_metrics(per_sample_results)

        expected_mean_dice = 0.6
        assert abs(aggregate["mean_dice"] - expected_mean_dice) < 1e-6

    def test_empty_returns_zero(self) -> None:
        """Empty input returns zeros."""
        aggregate = aggregate_metrics([])
        assert aggregate["mean_dice"] == 0.0
        assert aggregate["num_samples"] == 0


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
