"""Real FUSeg2021 contract and SPEC-02-01 integration checks."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image

from src.data.splitting import validate_manifest_for_training
from src.segmentation.config import validate_training_config
from src.segmentation.dataset import (
    WoundSegmentationDataset,
    load_manifest_samples,
    resolve_manifest_path,
)
from src.segmentation.model import BCEDiceLoss, LightweightUNet


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data/manifests/dataset_manifest.json"


def test_fuseg_manifest_contract_and_leakage_gate() -> None:
    manifest = validate_manifest_for_training(str(MANIFEST), require_real_data=True)
    assert manifest["dataset_name"] == "FUSeg2021"
    assert manifest["dataset_source_type"] == "real"
    assert manifest["split_summary"]["official_counts"] == {
        "train": 810,
        "validation": 200,
        "test": 200,
    }
    assert manifest["split_summary"]["leakage_analysis"]["leakage_test_passed"] is True
    assert manifest["split_summary"]["usable_test_samples"] == 0
    assert manifest["split_summary"]["patient_level_isolation_achieved"] is False


def test_real_fuseg_sample_loads_to_binary_contract() -> None:
    samples = load_manifest_samples(str(MANIFEST), split="train")
    dataset = WoundSegmentationDataset(
        samples=samples[:2],
        input_height=128,
        input_width=128,
        normalize_mean=[0.485, 0.456, 0.406],
        normalize_std=[0.229, 0.224, 0.225],
        is_training=False,
    )
    image, mask, sample_id = dataset[0]
    assert sample_id
    assert image.shape == (3, 128, 128)
    assert mask.shape == (1, 128, 128)
    assert image.dtype == torch.float32
    assert set(torch.unique(mask).tolist()).issubset({0.0, 1.0})


def test_train_augmentation_is_repeatable_for_seed_and_epoch() -> None:
    samples = load_manifest_samples(str(MANIFEST), split="train")
    first = WoundSegmentationDataset(
        samples=samples[:1],
        input_height=64,
        input_width=64,
        normalize_mean=[0.0, 0.0, 0.0],
        normalize_std=[1.0, 1.0, 1.0],
        is_training=True,
        horizontal_flip_prob=1.0,
        random_seed=9,
    )
    second = WoundSegmentationDataset(
        samples=samples[:1],
        input_height=64,
        input_width=64,
        normalize_mean=[0.0, 0.0, 0.0],
        normalize_std=[1.0, 1.0, 1.0],
        is_training=True,
        horizontal_flip_prob=1.0,
        random_seed=9,
    )
    image_a, mask_a, _ = first[0]
    image_b, mask_b, _ = second[0]
    assert torch.equal(image_a, image_b)
    assert torch.equal(mask_a, mask_b)


def test_model_and_loss_use_logits_contract() -> None:
    model = LightweightUNet(encoder_channels=[8, 16, 32, 64])
    logits = model(torch.randn(2, 3, 64, 64))
    targets = torch.zeros_like(logits)
    loss = BCEDiceLoss()(logits, targets)
    assert logits.shape == targets.shape == (2, 1, 64, 64)
    assert torch.isfinite(loss)
    assert torch.isfinite(logits).all()


def test_real_sample_alignment_is_preserved_through_synchronized_flip(tmp_path: Path) -> None:
    image_array = np.zeros((8, 8, 3), dtype=np.uint8)
    image_array[:, 0, 0] = 255
    mask_array = np.zeros((8, 8), dtype=np.uint8)
    mask_array[:, 0] = 255
    image_path = tmp_path / "aligned.png"
    mask_path = tmp_path / "aligned_mask.png"
    Image.fromarray(image_array, mode="RGB").save(image_path)
    Image.fromarray(mask_array, mode="L").save(mask_path)

    dataset = WoundSegmentationDataset(
        samples=[
            {
                "source_sample_id": "aligned",
                "image_path": str(image_path),
                "annotation_path": str(mask_path),
                "width": 8,
                "height": 8,
                "validation_status": "VALID",
            }
        ],
        input_height=8,
        input_width=8,
        normalize_mean=[0.0, 0.0, 0.0],
        normalize_std=[1.0, 1.0, 1.0],
        is_training=True,
        horizontal_flip_prob=1.0,
    )
    image, mask, _ = dataset[0]
    assert torch.all(image[0, :, -1] == 1.0)
    assert torch.all(mask[0, :, -1] == 1.0)
    assert torch.sum(image[0, :, :-1]) == 0.0
    assert torch.sum(mask[0, :, :-1]) == 0.0


def test_runtime_loader_rejects_mask_values_that_manifest_should_exclude(tmp_path: Path) -> None:
    image_path = tmp_path / "image.png"
    mask_path = tmp_path / "mask.png"
    Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8), mode="RGB").save(image_path)
    invalid_mask = np.zeros((8, 8), dtype=np.uint8)
    invalid_mask[2:4, 2:4] = 32
    Image.fromarray(invalid_mask, mode="L").save(mask_path)

    dataset = WoundSegmentationDataset(
        samples=[
            {
                "source_sample_id": "invalid-mask",
                "image_path": str(image_path),
                "annotation_path": str(mask_path),
                "width": 8,
                "height": 8,
                "validation_status": "VALID",
            }
        ],
        input_height=8,
        input_width=8,
        normalize_mean=[0.0, 0.0, 0.0],
        normalize_std=[1.0, 1.0, 1.0],
        is_training=False,
    )
    with pytest.raises(RuntimeError, match="invalid source mask values"):
        dataset[0]


def test_runtime_loader_rejects_image_mask_dimension_mismatch(tmp_path: Path) -> None:
    image_path = tmp_path / "image.png"
    mask_path = tmp_path / "mask.png"
    Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8), mode="RGB").save(image_path)
    Image.fromarray(np.zeros((7, 8), dtype=np.uint8), mode="L").save(mask_path)
    dataset = WoundSegmentationDataset(
        samples=[
            {
                "source_sample_id": "dimension-mismatch",
                "image_path": str(image_path),
                "annotation_path": str(mask_path),
                "width": 8,
                "height": 8,
                "validation_status": "VALID",
            }
        ],
        input_height=8,
        input_width=8,
        normalize_mean=[0.0, 0.0, 0.0],
        normalize_std=[1.0, 1.0, 1.0],
        is_training=False,
    )
    with pytest.raises(RuntimeError, match="image/mask size mismatch"):
        dataset[0]


def test_small_forward_backward_pass_has_finite_gradients() -> None:
    model = LightweightUNet(encoder_channels=[4, 8, 16, 32])
    logits = model(torch.randn(2, 3, 32, 32))
    targets = torch.zeros_like(logits)
    loss = BCEDiceLoss()(logits, targets)
    loss.backward()
    assert torch.isfinite(loss)
    assert all(
        parameter.grad is None or bool(torch.isfinite(parameter.grad).all())
        for parameter in model.parameters()
    )


def test_real_training_config_is_rejected_when_checkpoint_policy_changes() -> None:
    config = json.loads(
        (ROOT / "configs/training/baseline_segmentation_real.json").read_text(encoding="utf-8")
    )
    validate_training_config(config)
    config["checkpointing"]["checkpoint_selection_mode"] = "min"
    with pytest.raises(ValueError, match="maximum validation Dice"):
        validate_training_config(config)


def test_manifest_paths_can_be_remapped_to_a_kaggle_data_root(tmp_path: Path) -> None:
    mounted_root = tmp_path / "mounted_fuseg"
    image_path = mounted_root / "train/images/0001.png"
    mask_path = mounted_root / "train/labels/0001.png"
    image_path.parent.mkdir(parents=True)
    mask_path.parent.mkdir(parents=True)
    Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8), mode="RGB").save(image_path)
    Image.fromarray(np.zeros((8, 8), dtype=np.uint8), mode="L").save(mask_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "source_root": "source",
                "samples": [
                    {
                        "source_sample_id": "0001",
                        "split": "train",
                        "validation_status": "VALID",
                        "annotation_type": "wound_segmentation",
                        "image_path": "source/train/images/0001.png",
                        "annotation_path": "source/train/labels/0001.png",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    samples = load_manifest_samples(str(manifest_path), split="train", data_root=str(mounted_root))
    assert Path(samples[0]["image_path"]) == image_path.resolve()
    assert Path(samples[0]["annotation_path"]) == mask_path.resolve()


def test_relative_manifest_paths_are_not_shadowed_by_caller_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_dir = tmp_path / "manifest_dir"
    manifest_dir.mkdir()
    source_dir = manifest_dir / "images"
    source_dir.mkdir()
    source_path = source_dir / "sample.png"
    Image.fromarray(np.zeros((4, 4, 3), dtype=np.uint8), mode="RGB").save(source_path)

    shadow_dir = tmp_path / "caller" / "images"
    shadow_dir.mkdir(parents=True)
    shadow_path = shadow_dir / "sample.png"
    Image.fromarray(np.full((4, 4, 3), 255, dtype=np.uint8), mode="RGB").save(shadow_path)
    monkeypatch.chdir(tmp_path / "caller")

    resolved = resolve_manifest_path("images/sample.png", str(manifest_dir / "manifest.json"))
    assert resolved == source_path
