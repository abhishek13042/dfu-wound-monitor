"""Shared fixtures: a tiny, randomly initialised segmentation artifact.

The real SPEC-02-03 checkpoint (293 MB, gitignored) is never needed by the
test suite.  The fixture writes a ResNet18 U-Net (``pretrained=False``) with a
64x64 input, plus matching training and inference configs, once per session.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image

from src.segmentation.resnet_unet import ResNetUNet

DECODER = [32, 16, 16, 8, 8]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_artifact(root: Path, *, seed: int = 0, threshold: float = 0.4, min_area: int = 4) -> Path:
    """Write checkpoint + configs under ``root``; return the inference config path."""

    root.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(seed)
    model = ResNetUNet("resnet18", pretrained=False, decoder_channels=DECODER)
    checkpoint = root / "tiny.pth"
    torch.save({"model_state_dict": model.state_dict(), "epoch": 1, "best_metric_value": 0.5}, checkpoint)
    training = {
        "preprocessing": {"input_height": 64, "input_width": 64,
                          "normalize_mean": [0.485, 0.456, 0.406], "normalize_std": [0.229, 0.224, 0.225]},
        "model": {"encoder_name": "resnet18", "decoder_channels": DECODER},
    }
    training_path = root / "training.json"
    training_path.write_text(json.dumps(training), encoding="utf-8")
    inference = {
        "inference_config_version": "test-v1",
        "model": {
            "model_version": "tiny-test-model",
            "experiment_id": "TEST",
            "checkpoint_path": str(checkpoint),
            "checkpoint_sha256": _sha256(checkpoint),
            "training_config_path": str(training_path),
        },
        "postprocessing": {"threshold": threshold, "min_component_area": min_area, "tta": True},
        "input": {"allowed_formats": ["PNG", "JPEG"], "max_pixels": 4_000_000},
        "runtime": {"device": "cpu", "determinism_policy": "test"},
    }
    config_path = root / "inference.json"
    config_path.write_text(json.dumps(inference), encoding="utf-8")
    return config_path


@pytest.fixture(scope="session")
def tiny_inference_config(tmp_path_factory) -> Path:
    return write_artifact(tmp_path_factory.mktemp("artifact"))


@pytest.fixture(scope="session")
def tiny_engine(tiny_inference_config):
    from src.inference.engine import InferenceEngine

    return InferenceEngine.from_config(tiny_inference_config)


def textured_png(path: Path, size=(96, 80), seed: int = 1) -> Path:
    """A sharp, well-exposed synthetic image that passes the quality gate."""

    rng = np.random.default_rng(seed)
    height, width = size[1], size[0]
    base = np.full((height, width, 3), (170, 120, 100), dtype=np.float32)
    noise = rng.normal(0, 30, (height, width, 3))
    yy, xx = np.mgrid[:height, :width]
    wound = ((yy - height / 2) ** 2 + (xx - width / 2) ** 2) < (min(height, width) / 4) ** 2
    base[wound] = (150, 40, 40)
    Image.fromarray(np.clip(base + noise, 0, 255).astype(np.uint8)).save(path)
    return path


@pytest.fixture
def make_image(tmp_path):
    """Factory fixture: ``make_image(name, size=(w, h), seed=1)`` -> path to a quality-passing PNG."""

    def factory(name: str = "image.png", size=(96, 80), seed: int = 1) -> Path:
        return textured_png(tmp_path / name, size=size, seed=seed)

    return factory
