"""Targeted engineering regression tests for SPEC-02-01; no full training."""

from __future__ import annotations

import copy
import json
import random
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image
from torch.utils.data import DataLoader, TensorDataset

from scripts.run_kaggle_spec_02_01 import build_kaggle_config
from src.data.fuseg import build_fuseg_manifest
from src.segmentation.config import validate_training_config
from src.segmentation.model import BCEDiceLoss, LightweightUNet
from src.segmentation.trainer import (
    _write_progress_log,
    load_checkpoint,
    save_checkpoint,
    set_random_seeds,
)

ROOT = Path(__file__).resolve().parents[2]


def _config() -> dict:
    return json.loads((ROOT / "configs/training/baseline_segmentation_real.json").read_text())


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("training", "resume_checkpoint", 1),
        ("data", "data_root", 1),
        ("output", "representative_prediction_count", 0),
        ("checkpointing", "save_latest_for_resume", "true"),
        ("checkpointing", "save_best_only", False),
    ],
)
def test_invalid_runtime_config_is_rejected(section: str, field: str, value: object) -> None:
    config = _config()
    config[section][field] = value
    with pytest.raises(ValueError):
        validate_training_config(config)


def test_kaggle_entrypoint_uses_writable_outputs_and_keeps_baseline_settings(tmp_path: Path) -> None:
    base = _config()
    original = copy.deepcopy(base)
    config = build_kaggle_config(base, str(tmp_path / "data"), str(tmp_path / "output"))
    assert base == original
    assert config["model"] == base["model"]
    assert config["preprocessing"] == base["preprocessing"]
    assert config["training"]["persistent_workers"] is False
    assert config["training"]["num_workers"] == 2
    assert config["training"]["num_epochs"] == base["training"]["num_epochs"]
    assert Path(config["checkpointing"]["checkpoint_dir"]).is_relative_to(tmp_path / "output")
    for name in ("log_file", "model_metadata", "sanity_report", "sanity_panel", "experiment_record", "prediction_output_dir"):
        assert Path(config["output"][name]).is_relative_to(tmp_path / "output")


def test_checkpoint_restores_optimizer_scheduler_and_all_rng_streams(tmp_path: Path) -> None:
    set_random_seeds(7)
    model = torch.nn.Conv2d(3, 1, 1)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=1, gamma=0.5)
    optimizer.zero_grad()
    model(torch.ones(1, 3, 2, 2)).sum().backward()
    optimizer.step()
    scheduler.step()
    loader = DataLoader(TensorDataset(torch.arange(8)), shuffle=True, generator=torch.Generator().manual_seed(9))
    checkpoint = tmp_path / "roundtrip.pth"
    saved_weights = copy.deepcopy(model.state_dict())
    save_checkpoint(model, optimizer, 1, 0.25, {}, str(checkpoint), scheduler=scheduler, data_loader=loader)
    expected_random = random.random()
    expected_numpy = np.random.rand()
    expected_torch = torch.rand(4)
    expected_order = torch.cat([batch[0] for batch in loader])

    with torch.no_grad():
        model.weight.fill_(0)
    optimizer.param_groups[0]["lr"] = 99
    scheduler.step()
    set_random_seeds(100)
    metadata = load_checkpoint(str(checkpoint), model, torch.device("cpu"), optimizer, scheduler, loader, True)
    assert metadata["epoch"] == 1
    assert optimizer.param_groups[0]["lr"] == 0.005
    assert scheduler.last_epoch == 1
    assert optimizer.state
    assert all(torch.equal(value, model.state_dict()[key]) for key, value in saved_weights.items())
    assert random.random() == expected_random
    assert np.random.rand() == expected_numpy
    assert torch.equal(torch.rand(4), expected_torch)
    assert torch.equal(torch.cat([batch[0] for batch in loader]), expected_order)


def test_progress_log_is_structured_and_atomic(tmp_path: Path) -> None:
    log_path = tmp_path / "training_log.json"
    _write_progress_log(
        {"experiment_id": "progress-test", "output": {"log_file": str(log_path)}},
        "RUNNING",
        [{"epoch": 1, "val_dice": 0.2}],
        "best.pth",
        "latest.pth",
        1,
        0.2,
        {"val_dice": 0.2},
        {"device": "cpu"},
    )
    document = json.loads(log_path.read_text())
    assert document["status"] == "RUNNING"
    assert document["epoch_logs"][0]["epoch"] == 1
    assert not (tmp_path / ".training_log.json.running.tmp").exists()


def test_manifest_keeps_valid_duplicate_instead_of_invalid_annotation(tmp_path: Path) -> None:
    source = tmp_path / "source"
    for split in ("train", "validation", "test"):
        (source / split / "images").mkdir(parents=True)
        (source / split / "labels").mkdir()
    image = Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8))
    image.save(source / "train/images/0001.png")
    image.save(source / "validation/images/0002.png")
    Image.fromarray(np.full((8, 8), 32, dtype=np.uint8)).save(source / "train/labels/0001.png")
    Image.fromarray(np.zeros((8, 8), dtype=np.uint8)).save(source / "validation/labels/0002.png")
    manifest, _ = build_fuseg_manifest(source, tmp_path, "fixture", "fixture", "fixture")
    by_id = {record["source_sample_id"]: record for record in manifest["samples"]}
    assert by_id["0002"]["validation_status"] == "VALID"
    assert by_id["0001"]["validation_status"] != "VALID"


def test_unet_preserves_odd_rectangular_dimensions_for_single_sample() -> None:
    model = LightweightUNet([4, 8, 16, 32])
    logits = model(torch.randn(1, 3, 33, 49))
    assert logits.shape == (1, 1, 33, 49)
    assert torch.isfinite(logits).all()


def test_loss_empty_and_extreme_logits_have_finite_nonzero_gradients() -> None:
    logits = torch.tensor([[[[1000.0, -1000.0], [0.0, 0.0]]]], requires_grad=True)
    loss = BCEDiceLoss()(logits, torch.zeros_like(logits))
    loss.backward()
    assert torch.isfinite(loss)
    assert torch.isfinite(logits.grad).all()
    assert logits.grad[0, 0, 0, 0] > 0
