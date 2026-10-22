"""Tests for the Phase 02 real-data gates and independent evidence controls."""

import json
import random
from pathlib import Path

import numpy as np
import pytest
import torch
from torch.utils.data import DataLoader, TensorDataset

from scripts.verify_phase_02_metrics import (
    independently_compute_metrics,
    verify_saved_predictions,
)
from src.data.splitting import validate_manifest_for_training, verify_split_leakage
from src.segmentation.model import LightweightUNet
from src.segmentation.trainer import load_checkpoint, save_checkpoint


def _manifest_document(source_type: str = "real", leakage_passed: bool = True) -> dict:
    """Return a minimal manifest accepted by the real-data gate."""
    return {
        "manifest_version": "1.1.0",
        "dataset_name": "FUSeg2021",
        "dataset_source_type": source_type,
        "split_summary": {
            "train_samples": 1,
            "val_samples": 1,
            "test_samples": 1,
            "leakage_analysis": {"leakage_test_passed": leakage_passed},
        },
        "samples": [
            {"source_sample_id": "TRAIN", "split": "train"},
            {"source_sample_id": "VAL", "split": "val"},
            {"source_sample_id": "TEST", "split": "test"},
        ],
    }


def test_real_data_gate_rejects_synthetic_manifest(tmp_path: Path) -> None:
    """The historical demo cannot enter final Phase 02 training."""
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest_document("synthetic_demo")))

    with pytest.raises(RuntimeError, match="dataset_source_type='real'"):
        validate_manifest_for_training(str(manifest_path))


def test_real_data_gate_rejects_failed_leakage(tmp_path: Path) -> None:
    """A real manifest with failed leakage checks cannot start training."""
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest_document("real", False)))

    with pytest.raises(RuntimeError, match="leakage validation"):
        validate_manifest_for_training(str(manifest_path))


def test_real_data_gate_recomputes_cached_leakage_report(tmp_path: Path) -> None:
    """A stale passing report cannot override overlapping sample checksums."""
    manifest = _manifest_document("real", True)
    manifest["samples"][0]["checksum_sha256"] = "same-image"
    manifest["samples"][1]["checksum_sha256"] = "same-image"
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(RuntimeError, match="recomputed manifest leakage"):
        validate_manifest_for_training(str(manifest_path))


def test_leakage_checker_detects_annotation_and_exam_overlap() -> None:
    """Annotation and examination duplication are hard leakage failures."""
    records = [
        {
            "source_sample_id": "A",
            "split": "train",
            "checksum_sha256": "image-a",
            "annotation_checksum_sha256": "mask-shared",
            "exam_id": "exam-shared",
        },
        {
            "source_sample_id": "B",
            "split": "val",
            "checksum_sha256": "image-b",
            "annotation_checksum_sha256": "mask-shared",
            "exam_id": "exam-shared",
        },
        {
            "source_sample_id": "C",
            "split": "test",
            "checksum_sha256": "image-c",
            "annotation_checksum_sha256": "mask-c",
            "exam_id": "exam-c",
        },
    ]
    report = verify_split_leakage(records)

    assert report["leakage_test_passed"] is False
    assert report["annotation_checksum_leakage_detected"] is True
    assert report["exam_leakage_detected"] is True


def test_independent_metric_formula_and_saved_artifact_verification(tmp_path: Path) -> None:
    """Independent formulas agree with an evaluator-shaped result document."""
    ground_truth = np.zeros((4, 4), dtype=np.uint8)
    ground_truth[:2, :2] = 1
    prediction = np.zeros((4, 4), dtype=np.uint8)
    prediction[:2, :1] = 1
    prediction[3:, 3:] = 1

    expected = independently_compute_metrics(prediction, ground_truth)
    assert expected["true_positives"] == 2
    assert expected["false_positives"] == 1
    assert expected["false_negatives"] == 2

    predictions_dir = tmp_path / "predictions"
    predictions_dir.mkdir()
    np.savez_compressed(
        predictions_dir / "SAMPLE.npz",
        sample_id=np.array("SAMPLE"),
        prediction_probability=prediction.astype(np.float32),
        prediction_binary=prediction,
        ground_truth_mask=ground_truth,
    )
    evaluation_path = tmp_path / "evaluation.json"
    evaluation_path.write_text(
        json.dumps({"per_sample_results": [{"sample_id": "SAMPLE", **expected}]})
    )

    report = verify_saved_predictions(
        predictions_dir=str(predictions_dir),
        evaluation_results_path=str(evaluation_path),
    )
    assert report["verification_status"] == "PASS"
    assert report["production_metric_module_used"] is False


def test_checkpoint_round_trip_and_experiment_record() -> None:
    """Checkpoint metadata and the blocked experiment record remain readable."""
    model = LightweightUNet(encoder_channels=[8, 16, 32, 64])
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    loader_generator = torch.Generator().manual_seed(123)
    loader = DataLoader(TensorDataset(torch.zeros(2, 1)), generator=loader_generator)

    checkpoint_path = Path("/tmp/omnirush/phase02-test-checkpoint.pth")
    save_checkpoint(
        model=model,
        optimizer=optimizer,
        epoch=1,
        val_dice=0.25,
        config={
            "experiment_id": "test",
            "model": {"architecture": "LightweightUNet", "encoder_channels": [8, 16, 32, 64]},
            "preprocessing": {"input_height": 64, "input_width": 64},
            "loss": {"name": "BCEDiceLoss"},
            "training": {"random_seed": 42},
        },
        checkpoint_path=str(checkpoint_path),
        metadata={"best_epoch": 1},
        data_loader=loader,
    )
    saved_generator_state = loader.generator.get_state().clone()
    random.seed(999)
    np.random.seed(999)
    torch.manual_seed(999)
    metadata = load_checkpoint(
        str(checkpoint_path),
        model,
        torch.device("cpu"),
        data_loader=loader,
        restore_rng=True,
    )
    assert metadata["epoch"] == 1
    assert metadata["val_dice"] == 0.25
    assert metadata["metadata"]["best_epoch"] == 1
    assert torch.equal(loader.generator.get_state(), saved_generator_state)

    record_path = Path("reports/experiments/P02-baseline-unet-bce-dice-v1_experiment_record.json")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["status"] == "IMPLEMENTATION_COMPLETE_REAL_DATA_BLOCKED"
    assert record["test_metrics"] is None
