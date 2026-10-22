"""P03-S01 inference and model artifact contract tests."""

from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image

from src.inference.engine import DEFAULT_INFERENCE_CONFIG, InferenceConfig, InferenceEngine, InferenceRequest
from src.inference.errors import (
    CheckpointChecksumError,
    CheckpointCorruptError,
    CheckpointIncompatibleError,
    CheckpointMissingError,
    ConfigError,
    InputError,
    InputMissingError,
    InputTooLargeError,
    InputUnreadableError,
    UnsupportedFormatError,
)
from src.preprocessing.decode import decode_image
from src.segmentation.inference import predict_native_probabilities, remove_small_components


def _rewrite(config_path: Path, tmp_path: Path, mutate) -> Path:
    document = json.loads(config_path.read_text(encoding="utf-8"))
    mutate(document)
    target = tmp_path / "inference_mutated.json"
    target.write_text(json.dumps(document), encoding="utf-8")
    return target


# --- REQ-P03-S01-001: training preprocessing reused, no overrides -------------

def test_shipped_config_reads_preprocessing_from_training_config():
    config = InferenceConfig.load(DEFAULT_INFERENCE_CONFIG)
    training = json.loads(config.training_config_path.read_text(encoding="utf-8"))
    prep = training["preprocessing"]
    assert (config.input_height, config.input_width) == (prep["input_height"], prep["input_width"])
    assert list(config.normalize_mean) == prep["normalize_mean"]
    assert list(config.normalize_std) == prep["normalize_std"]
    assert config.encoder_name == training["model"]["encoder_name"]
    assert (config.threshold, config.min_component_area, config.tta) == (0.40, 128, True)


def test_engine_matches_training_evaluation_path(tiny_engine, make_image):
    """The engine must produce exactly what SPEC-02-03 evaluation produced for the same model."""

    path = make_image("eval.png", size=(90, 70))
    cfg = tiny_engine.config
    reference = predict_native_probabilities(
        tiny_engine.model, [path], cfg.input_height, cfg.input_width, list(cfg.normalize_mean),
        list(cfg.normalize_std), tiny_engine.device, tta=cfg.tta,
    )[0].astype(np.float32)
    result = tiny_engine.predict(InferenceRequest(path))
    # the evaluation path stores float16; compare at that precision
    np.testing.assert_allclose(result.probability_mask, reference, atol=1e-3)
    expected = remove_small_components((result.probability_mask >= cfg.threshold).astype(np.uint8),
                                       cfg.min_component_area)
    np.testing.assert_array_equal(result.binary_mask, expected)


# --- REQ-P03-S01-002: outputs and provenance --------------------------------

def test_result_shapes_values_and_provenance(tiny_engine, make_image):
    path = make_image("p.png", size=(100, 60))
    result = tiny_engine.predict(InferenceRequest(path, request_id="req-1"))
    assert result.probability_mask.shape == result.binary_mask.shape == (60, 100)
    assert result.probability_mask.dtype == np.float32
    assert 0.0 <= result.probability_mask.min() and result.probability_mask.max() <= 1.0
    assert set(np.unique(result.binary_mask)) <= {0, 1}
    prov = result.provenance
    assert prov["request_id"] == "req-1"
    assert prov["model"]["model_version"] == "tiny-test-model"
    assert len(prov["model"]["checkpoint_sha256"]) == 64 and prov["model"]["checksum_verified"]
    assert len(prov["model"]["inference_config_sha256"]) == 64
    assert len(prov["model"]["training_config_sha256"]) == 64
    assert prov["input"]["sha256"] == decode_image(path).sha256
    assert (prov["input"]["width"], prov["input"]["height"]) == (100, 60)
    assert prov["preprocessing"]["input_height"] == 64
    assert prov["postprocessing"]["threshold"] == 0.4
    assert {"device", "torch_version", "duration_ms", "completed_at"} <= set(prov["execution"])
    json.dumps(result.summary())  # provenance must be JSON-serialisable


def test_threshold_override_is_recorded(tiny_engine, make_image):
    path = make_image()
    result = tiny_engine.predict(InferenceRequest(path, threshold=0.7))
    assert result.provenance["postprocessing"]["threshold"] == 0.7
    assert result.provenance["postprocessing"]["frozen_threshold"] == 0.4
    assert any(w["code"] == "THRESHOLD_OVERRIDE" for w in result.warnings)
    with pytest.raises(InputError):
        tiny_engine.predict(InferenceRequest(path, threshold=1.5))


def test_bytes_input_and_exif_orientation(tiny_engine, make_image):
    path = make_image("o.png", size=(80, 48))
    image = Image.open(path).convert("RGB")
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 degrees clockwise on display
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif.tobytes())
    result = tiny_engine.predict(InferenceRequest(buffer.getvalue()))
    assert result.binary_mask.shape == (80, 48)  # displayed orientation
    assert any(w["code"] == "EXIF_ORIENTATION_APPLIED" for w in result.warnings)
    assert result.provenance["input"]["reference"] == "<bytes>"


# --- REQ-P03-S01-003: typed errors ------------------------------------------

def test_input_errors_are_typed(tiny_engine, tmp_path):
    with pytest.raises(InputMissingError):
        tiny_engine.predict(InferenceRequest(tmp_path / "absent.png"))
    with pytest.raises(InputMissingError):
        tiny_engine.predict(InferenceRequest(b""))
    corrupt = tmp_path / "corrupt.png"
    corrupt.write_bytes(b"\x89PNG\r\n\x1a\n" + b"garbage" * 20)
    with pytest.raises(InputUnreadableError) as error:
        tiny_engine.predict(InferenceRequest(corrupt))
    assert error.value.category == "INPUT" and error.value.to_dict()["code"] == "INPUT_UNREADABLE"
    gif = tmp_path / "x.gif"
    Image.new("RGB", (64, 64)).save(gif)
    with pytest.raises(UnsupportedFormatError):
        tiny_engine.predict(InferenceRequest(gif))
    big = tmp_path / "big.png"
    Image.new("RGB", (2100, 2000)).save(big)  # 4.2 MP > 4 MP fixture limit
    with pytest.raises(InputTooLargeError):
        tiny_engine.predict(InferenceRequest(big))


def test_checkpoint_errors_are_typed(tiny_inference_config, tmp_path):
    missing = _rewrite(tiny_inference_config, tmp_path,
                       lambda d: d["model"].__setitem__("checkpoint_path", str(tmp_path / "none.pth")))
    with pytest.raises(CheckpointMissingError):
        InferenceEngine.from_config(missing)

    wrong_hash = _rewrite(tiny_inference_config, tmp_path,
                          lambda d: d["model"].__setitem__("checkpoint_sha256", "0" * 64))
    with pytest.raises(CheckpointChecksumError):
        InferenceEngine.from_config(wrong_hash)

    corrupt = tmp_path / "corrupt.pth"
    corrupt.write_bytes(b"not a checkpoint")
    import hashlib
    digest = hashlib.sha256(corrupt.read_bytes()).hexdigest()

    def point_to_corrupt(d):
        d["model"]["checkpoint_path"] = str(corrupt)
        d["model"]["checkpoint_sha256"] = digest
    with pytest.raises(CheckpointCorruptError):
        InferenceEngine.from_config(_rewrite(tiny_inference_config, tmp_path, point_to_corrupt))

    incompatible = tmp_path / "incompatible.pth"
    torch.save({"model_state_dict": {"unexpected.weight": torch.zeros(1)}}, incompatible)
    digest = hashlib.sha256(incompatible.read_bytes()).hexdigest()

    def point_to_incompatible(d):
        d["model"]["checkpoint_path"] = str(incompatible)
        d["model"]["checkpoint_sha256"] = digest
    with pytest.raises(CheckpointIncompatibleError):
        InferenceEngine.from_config(_rewrite(tiny_inference_config, tmp_path, point_to_incompatible))


@pytest.mark.parametrize("mutate", [
    lambda d: d["postprocessing"].__setitem__("threshold", 1.2),
    lambda d: d["postprocessing"].__setitem__("min_component_area", -1),
    lambda d: d["model"].__setitem__("checkpoint_sha256", "abc"),
    lambda d: d.pop("postprocessing"),
    lambda d: d["model"].__setitem__("training_config_path", "missing.json"),
])
def test_malformed_config_is_rejected(tiny_inference_config, tmp_path, mutate):
    with pytest.raises(ConfigError):
        InferenceConfig.load(_rewrite(tiny_inference_config, tmp_path, mutate))


# --- REQ-P03-S01-004: determinism ---------------------------------------------

def test_repeated_inference_is_bit_identical(tiny_engine, tiny_inference_config, make_image):
    path = make_image("d.png")
    first = tiny_engine.predict(InferenceRequest(path))
    second = tiny_engine.predict(InferenceRequest(path))
    reloaded = InferenceEngine.from_config(tiny_inference_config).predict(InferenceRequest(path))
    for other in (second, reloaded):
        np.testing.assert_array_equal(first.probability_mask, other.probability_mask)
        np.testing.assert_array_equal(first.binary_mask, other.binary_mask)
