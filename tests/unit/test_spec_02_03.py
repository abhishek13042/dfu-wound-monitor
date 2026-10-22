"""Unit tests for the SPEC-02-03 held-out split, metrics, model and training engine."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image

from src.data.heldout_split import HELDOUT_MANIFEST_VERSION, derive_heldout_manifest, sample_key
from src.data.near_duplicates import (
    compute_phash,
    find_near_duplicate_pairs,
    group_near_duplicates,
    hamming_distance,
)
from src.segmentation.augmentation import SegmentationAugmenter, validate_augmentation_config
from src.segmentation.config_strong import validate_strong_config
from src.segmentation.dataset import WoundSegmentationDataset
from src.segmentation.inference import remove_small_components, score_predictions, tune_postprocessing
from src.segmentation.metrics import (
    aggregate_metrics,
    compute_binary_segmentation_metrics,
    compute_hd95,
)
from src.segmentation.model import BCEDiceLoss
from src.segmentation.resnet_unet import ResNetUNet
from src.segmentation.strong_trainer import build_warmup_cosine_scheduler, train_strong_model

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STRONG_CONFIG = PROJECT_ROOT / "configs" / "training" / "segmentation_resnet34_unet_512.json"


def _textured_image(seed: int, size: int = 64) -> Image.Image:
    rng = np.random.default_rng(seed)
    return Image.fromarray(rng.integers(0, 256, (size, size, 3), dtype=np.uint8))


# --- near duplicates -------------------------------------------------------

def test_phash_is_robust_to_mild_changes_and_separates_different_images():
    base = _textured_image(1, 128)
    resized = base.resize((96, 96)).resize((128, 128))
    other = _textured_image(2, 128)
    assert hamming_distance(compute_phash(base), compute_phash(resized)) <= 8
    assert hamming_distance(compute_phash(base), compute_phash(other)) > 8


def test_near_duplicate_groups_are_transitive():
    hashes = {"a": 0b0, "b": 0b1, "c": 0b11, "d": (1 << 63) - 1}
    pairs = find_near_duplicate_pairs(hashes, max_distance=1)
    groups = group_near_duplicates(list(hashes), pairs)
    assert sorted(sorted(group) for group in groups) == [["a", "b", "c"], ["d"]]


# --- held-out manifest -----------------------------------------------------

def _record(official_split: str, sample_id: str, empty: bool = False, annotation: str = "wound_segmentation"):
    split = {"train": "train", "validation": "val", "test": "test"}[official_split]
    return {
        "dataset_name": "FUSeg2021",
        "source_sample_id": sample_id,
        "official_split": official_split,
        "split": split,
        "validation_status": "VALID",
        "annotation_type": annotation,
        "quality": {"mask_empty": empty},
    }


def _synthetic_manifest():
    samples = [_record("train", f"t{i:02d}", empty=i < 4) for i in range(40)]
    samples += [_record("validation", f"v{i:02d}") for i in range(10)]
    samples += [_record("test", f"u{i:02d}", annotation="unlabeled_test") for i in range(3)]
    manifest = {"dataset_name": "FUSeg2021", "samples": samples, "split_summary": {}}
    # Distinct hashes far apart, except: t00~t01 (train group), t10~v00 (cross split).
    hashes = {sample_key(r): (index * 0x9E3779B97F4A7C15) & ((1 << 64) - 1) for index, r in enumerate(samples)}
    hashes["train/t01"] = hashes["train/t00"] ^ 0b1
    hashes["train/t10"] = hashes["validation/v00"] ^ 0b11
    return manifest, hashes


def test_derive_heldout_manifest_roles_and_guards():
    manifest, hashes = _synthetic_manifest()
    original = copy.deepcopy(manifest)
    derived, report = derive_heldout_manifest(manifest, hashes, internal_val_fraction=0.2, seed=0, max_hamming_distance=2)
    assert manifest == original
    assert derived["manifest_version"] == HELDOUT_MANIFEST_VERSION
    by_id = {r["source_sample_id"]: r for r in derived["samples"]}

    assert all(by_id[f"v{i:02d}"]["split"] == "test" for i in range(10))
    assert all(by_id[f"u{i:02d}"]["split"] == "unlabeled_test" for i in range(3))
    assert by_id["t10"]["validation_status"] == "QUARANTINED"
    assert by_id["t10"]["issue_category"] == "near_duplicate_of_heldout_test"
    assert report["train_quarantined_near_duplicate_of_test"] == ["train/t10"]
    assert by_id["t00"]["split"] == by_id["t01"]["split"]

    counts = report["counts"]
    assert counts["test"] == 10 and counts["train"] + counts["val"] == 39
    assert 5 <= counts["val"] <= 10
    assert report["empty_mask_counts"]["val"] >= 1


def test_derive_heldout_manifest_is_seed_deterministic():
    manifest, hashes = _synthetic_manifest()
    first, _ = derive_heldout_manifest(manifest, hashes, seed=7, max_hamming_distance=2)
    second, _ = derive_heldout_manifest(manifest, hashes, seed=7, max_hamming_distance=2)
    assert [r["split"] for r in first["samples"]] == [r["split"] for r in second["samples"]]


def test_committed_heldout_manifest_has_no_exact_leakage():
    path = PROJECT_ROOT / "data" / "manifests" / "fuseg2021_heldout_manifest.json"
    if not path.exists():
        pytest.skip("held-out manifest not built")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    usable = [s for s in manifest["samples"] if s["validation_status"] == "VALID" and s["split"] in {"train", "val", "test"}]
    by_split = {split: {s["checksum_sha256"] for s in usable if s["split"] == split} for split in ("train", "val", "test")}
    assert not by_split["train"] & by_split["val"]
    assert not by_split["train"] & by_split["test"]
    assert not by_split["val"] & by_split["test"]
    assert all(s["official_split"] == "validation" for s in usable if s["split"] == "test")


# --- metrics ---------------------------------------------------------------

def test_pooled_and_nonempty_metrics():
    gt_a = np.zeros((10, 10), np.uint8)
    gt_a[:5] = 1
    pred_a = gt_a.copy()
    gt_empty = np.zeros((10, 10), np.uint8)
    pred_fp = np.zeros((10, 10), np.uint8)
    pred_fp[0, 0] = 1
    results = []
    for sample_id, pred, gt in (("a", pred_a, gt_a), ("e", pred_fp, gt_empty)):
        metrics = compute_binary_segmentation_metrics(pred, gt)
        results.append({"sample_id": sample_id, "wound_area_ratio_ground_truth": float(gt.mean()), **metrics})
    aggregate = aggregate_metrics(results)
    assert aggregate["pooled_dice"] == pytest.approx(2 * 50 / (2 * 50 + 1))
    assert aggregate["nonempty_num_samples"] == 1
    assert aggregate["nonempty_mean_dice"] == pytest.approx(1.0)
    assert aggregate["empty_false_positive_rate"] == pytest.approx(1.0)


def test_hd95_edge_cases():
    empty = np.zeros((20, 20), np.uint8)
    square = empty.copy()
    square[5:10, 5:10] = 1
    shifted = np.roll(square, 3, axis=1)
    assert compute_hd95(empty, empty) == 0.0
    assert compute_hd95(square, empty) is None
    assert compute_hd95(square, square) == 0.0
    assert compute_hd95(shifted, square) == pytest.approx(3.0)


# --- model and augmentation --------------------------------------------------

def test_resnet_unet_forward_shape_and_param_groups():
    model = ResNetUNet("resnet34", pretrained=False).eval()
    with torch.no_grad():
        out = model(torch.randn(2, 3, 64, 96))
    assert out.shape == (2, 1, 64, 96)
    total = sum(p.numel() for p in model.parameters())
    assert total == sum(p.numel() for p in model.encoder_parameters()) + sum(
        p.numel() for p in model.decoder_parameters()
    )
    with pytest.raises(ValueError):
        model(torch.randn(1, 3, 50, 64))


def test_augmenter_is_deterministic_and_keeps_masks_binary():
    augmenter = SegmentationAugmenter()
    image = torch.rand(3, 64, 64)
    mask = (torch.rand(1, 64, 64) > 0.7).float()
    outputs = []
    for _ in range(2):
        generator = torch.Generator().manual_seed(123)
        outputs.append(augmenter(image.clone(), mask.clone(), generator))
    assert torch.equal(outputs[0][0], outputs[1][0]) and torch.equal(outputs[0][1], outputs[1][1])
    for seed in range(10):
        aug_image, aug_mask = augmenter(image, mask, torch.Generator().manual_seed(seed))
        assert aug_image.shape == image.shape and aug_mask.shape == mask.shape
        assert set(torch.unique(aug_mask).tolist()) <= {0.0, 1.0}
        assert aug_image.min() >= 0 and aug_image.max() <= 1


def test_augmentation_config_rejects_unknown_keys():
    with pytest.raises(ValueError):
        validate_augmentation_config({"unknown_transform": 1})


def _write_pair(directory: Path, name: str, size: int = 64) -> dict:
    image_path = directory / f"{name}.png"
    mask_path = directory / f"{name}_mask.png"
    _textured_image(hash(name) % 1000, size).save(image_path)
    mask = np.zeros((size, size), np.uint8)
    mask[size // 4: size // 2, size // 4: size // 2] = 255
    Image.fromarray(mask).save(mask_path)
    return {"source_sample_id": name, "image_path": str(image_path), "annotation_path": str(mask_path),
            "width": size, "height": size, "validation_status": "VALID"}


def test_dataset_uses_augmenter_reproducibly(tmp_path):
    samples = [_write_pair(tmp_path, f"s{i}") for i in range(2)]
    kwargs = dict(input_height=64, input_width=64, normalize_mean=[0.5] * 3, normalize_std=[0.25] * 3,
                  is_training=True, augmenter=SegmentationAugmenter())
    first = WoundSegmentationDataset(samples, **kwargs)
    second = WoundSegmentationDataset(samples, **kwargs)
    image_a, mask_a, _ = first[1]
    image_b, mask_b, _ = second[1]
    assert torch.equal(image_a, image_b) and torch.equal(mask_a, mask_b)
    first.set_epoch(5)
    image_c, _, _ = first[1]
    assert not torch.equal(image_a, image_c)


# --- inference / post-processing --------------------------------------------

def test_remove_small_components():
    mask = np.zeros((20, 20), np.uint8)
    mask[0:2, 0:2] = 1
    mask[10:18, 10:18] = 1
    cleaned = remove_small_components(mask, 10)
    assert cleaned[0:2, 0:2].sum() == 0 and cleaned[10:18, 10:18].sum() == 64
    assert np.array_equal(remove_small_components(mask, 0), mask)


def test_tune_postprocessing_prefers_cleanup_and_scores():
    gt = np.zeros((32, 32), np.uint8)
    gt[8:24, 8:24] = 1
    prob = gt.astype(np.float32) * 0.9
    prob[0:2, 0:2] = 0.9
    aggregate, per_sample = score_predictions(["x"], [prob], [gt], 0.5, 0, include_hd95=True)
    assert aggregate["mean_dice"] < 1.0 and per_sample[0]["hd95"] is not None
    tuning = tune_postprocessing(["x"], [prob], [gt], thresholds=[0.5], min_areas=[0, 16])
    assert tuning["best"]["min_component_area"] == 16
    assert tuning["best"]["mean_dice"] == pytest.approx(1.0)


def test_warmup_cosine_schedule():
    optimizer = torch.optim.SGD([torch.nn.Parameter(torch.zeros(1))], lr=1.0)
    scheduler = build_warmup_cosine_scheduler(optimizer, total_steps=100, warmup_steps=10, min_lr_ratio=0.01)
    lrs = []
    for _ in range(100):
        lrs.append(optimizer.param_groups[0]["lr"])
        optimizer.step()
        scheduler.step()
    assert lrs[0] == pytest.approx(0.1)
    assert lrs[9] == pytest.approx(1.0)
    assert lrs[-1] == pytest.approx(0.01, abs=0.01)
    assert all(a >= b for a, b in zip(lrs[10:], lrs[11:]))


# --- configuration -----------------------------------------------------------

def test_strong_config_accepts_committed_config():
    config = json.loads(STRONG_CONFIG.read_text(encoding="utf-8"))
    validate_strong_config(config)
    assert config["model"]["pretrained"] is True


@pytest.mark.parametrize(
    "path,value",
    [
        (("specification",), "SPEC-02-01"),
        (("data", "required_manifest_version"), "fuseg2021-official-v1"),
        (("preprocessing", "input_height"), 500),
        (("evaluation", "tune_postprocessing_on"), "test"),
        (("training", "ema_decay"), 1.0),
        (("augmentation", "validation_and_test"), "flips"),
        (("checkpointing", "checkpoint_selection_metric"), "test_dice"),
    ],
)
def test_strong_config_rejects_unsafe_values(path, value):
    config = json.loads(STRONG_CONFIG.read_text(encoding="utf-8"))
    target = config
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        validate_strong_config(config)


# --- training engine ---------------------------------------------------------

def test_train_strong_model_cpu_smoke(tmp_path):
    samples = [_write_pair(tmp_path, f"s{i}") for i in range(4)]
    common = dict(input_height=64, input_width=64, normalize_mean=[0.5] * 3, normalize_std=[0.25] * 3)
    train_ds = WoundSegmentationDataset(samples[:3], is_training=True, augmenter=SegmentationAugmenter(), **common)
    val_ds = WoundSegmentationDataset(samples[3:], is_training=False, **common)
    train_loader = torch.utils.data.DataLoader(train_ds, batch_size=2, shuffle=True)
    val_loader = torch.utils.data.DataLoader(val_ds, batch_size=2)
    config = json.loads(STRONG_CONFIG.read_text(encoding="utf-8"))
    config["training"].update(num_epochs=2, num_workers=0, persistent_workers=False,
                              scheduler={"name": "warmup_cosine", "warmup_epochs": 1, "min_lr_ratio": 0.01})
    config["checkpointing"]["checkpoint_dir"] = str(tmp_path / "ckpt")
    config["output"]["log_file"] = str(tmp_path / "log.json")
    model = ResNetUNet("resnet18", pretrained=False)
    summary = train_strong_model(model, BCEDiceLoss(), train_loader, val_loader, config, torch.device("cpu"))
    assert summary["status"] == "COMPLETED_TRAINING"
    assert len(summary["epoch_logs"]) == 2
    assert (tmp_path / "ckpt" / config["checkpointing"]["checkpoint_filename_template"]).exists()
    log = json.loads((tmp_path / "log.json").read_text(encoding="utf-8"))
    assert log["test_evaluation"] == "NOT_RUN_DURING_TRAINING"

    # Resume continues from the latest checkpoint without repeating epochs.
    config["training"].update(num_epochs=3,
                              resume_checkpoint=str(tmp_path / "ckpt" / config["checkpointing"]["latest_checkpoint_filename_template"]))
    resumed = train_strong_model(ResNetUNet("resnet18", pretrained=False), BCEDiceLoss(),
                                 train_loader, val_loader, config, torch.device("cpu"))
    assert [log["epoch"] for log in resumed["epoch_logs"]] == [1, 2, 3]


def test_ema_warmup_tracks_early_weights():
    from src.segmentation.strong_trainer import build_ema

    model = torch.nn.Sequential(torch.nn.Linear(2, 2), torch.nn.BatchNorm1d(2))
    ema = build_ema(model, 0.999)
    for _ in range(20):
        with torch.no_grad():
            for parameter in model.parameters():
                parameter.add_(1.0)
        ema.update_parameters(model)
    gap = (model[0].weight - ema.module[0].weight).abs().max().item()
    # Plain 0.999 EMA would lag by ~19; the warmed-up decay keeps it within a few steps.
    assert gap < 6.0
