"""P07-S06 ONNX export and serving: export round trip, interface parity, hash refusal, engine choice."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from src.inference.engine import InferenceEngine, InferenceRequest, InferenceResult
from src.inference.errors import CheckpointChecksumError, CheckpointMissingError, ConfigError
from src.inference.onnx_engine import OnnxEngine, create_engine, engine_choice

pytest.importorskip("onnxruntime")
export_onnx = pytest.importorskip("scripts.deployment.export_onnx")


@pytest.fixture(scope="module")
def tiny_onnx_config(tiny_inference_config, tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("onnx")
    config = root / "inference_onnx.json"
    assert export_onnx.main(["--config", str(tiny_inference_config), "--output", str(root / "tiny.onnx"),
                             "--onnx-config", str(config), "--report", str(root / "report.json")]) == 0
    return config


def test_export_records_hashes_and_opset(tiny_onnx_config, tiny_inference_config):
    block = json.loads(tiny_onnx_config.read_text())["onnx"]
    report = json.loads((tiny_onnx_config.parent / "report.json").read_text())
    assert block["opset"] == 17 and report["dynamic_axes"] == ["batch", "height", "width"]
    assert len(block["model_sha256"]) == 64 and block["model_sha256"] == report["model_sha256"]
    checkpoint = json.loads(tiny_inference_config.read_text())["model"]["checkpoint_sha256"]
    assert block["source_checkpoint_sha256"] == checkpoint


def test_export_is_byte_reproducible(tiny_onnx_config, tiny_inference_config, tmp_path):
    again = tmp_path / "again.onnx"
    export_onnx.main(["--config", str(tiny_inference_config), "--output", str(again),
                      "--onnx-config", str(tmp_path / "c.json"), "--report", str(tmp_path / "r.json")])
    assert json.loads((tmp_path / "c.json").read_text())["onnx"]["model_sha256"] == \
        json.loads(tiny_onnx_config.read_text())["onnx"]["model_sha256"]


def test_same_result_type_and_matching_masks(tiny_onnx_config, tiny_engine, make_image):
    onnx_engine = OnnxEngine.from_config(tiny_onnx_config)
    for size in ((96, 80), (130, 70)):  # resized to the model input, so dynamic axes are not needed here
        image = make_image(f"in_{size[0]}.png", size=size)
        reference = tiny_engine.predict(InferenceRequest(image))
        result = onnx_engine.predict(InferenceRequest(image))
        assert isinstance(result, InferenceResult)
        assert result.probability_mask.dtype == np.float32 and result.binary_mask.dtype == np.uint8
        assert result.probability_mask.shape == reference.probability_mask.shape == (size[1], size[0])
        assert np.abs(result.probability_mask - reference.probability_mask).max() < 1e-4
        assert [w["code"] for w in result.warnings] == [w["code"] for w in reference.warnings]
        assert set(result.provenance) == set(reference.provenance)
    described = onnx_engine.describe()
    assert described["model_version"].endswith("-onnx-v1") and described["runtime"] == "onnxruntime"
    assert described["onnx_opset"] == 17


def test_tta_runs_one_session_call_per_view(tiny_onnx_config, make_image):
    engine = OnnxEngine.from_config(tiny_onnx_config)
    calls = []
    run = engine.model.run
    engine.model = type("Spy", (), {"run": lambda self, *a: calls.append(a) or run(*a)})()
    engine.predict(InferenceRequest(make_image()))
    assert len(calls) == 4


def test_dynamic_height_and_width(tiny_onnx_config):
    engine = OnnxEngine.from_config(tiny_onnx_config)
    for height, width in ((64, 64), (96, 128)):
        logits = engine.model.run(None, {engine.input_name: np.zeros((1, 3, height, width), np.float32)})[0]
        assert logits.shape == (1, 1, height, width)


def test_hash_mismatch_refuses_to_load(tiny_onnx_config, tmp_path):
    raw = json.loads(tiny_onnx_config.read_text())
    raw["onnx"]["model_sha256"] = "0" * 64
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw))
    with pytest.raises(CheckpointChecksumError):
        OnnxEngine.from_config(bad)
    raw["onnx"]["model_path"] = str(tmp_path / "missing.onnx")
    bad.write_text(json.dumps(raw))
    with pytest.raises(CheckpointMissingError):
        OnnxEngine.from_config(bad)


def test_config_without_onnx_block_is_refused(tiny_inference_config):
    with pytest.raises(ConfigError):
        OnnxEngine.from_config(tiny_inference_config)


def test_engine_choice_defaults_to_pytorch(monkeypatch, tiny_inference_config, tiny_onnx_config):
    monkeypatch.delenv("DFU_INFERENCE_ENGINE", raising=False)
    assert engine_choice() == "pytorch"
    assert type(create_engine(tiny_inference_config)) is InferenceEngine
    monkeypatch.setenv("DFU_INFERENCE_ENGINE", "onnx")
    assert isinstance(create_engine(tiny_onnx_config), OnnxEngine)
    monkeypatch.setenv("DFU_INFERENCE_ENGINE", "tensorrt")
    with pytest.raises(ConfigError):
        engine_choice()


def test_damaged_file_is_a_typed_error(tiny_onnx_config, tmp_path):
    from src.inference.errors import CheckpointCorruptError

    damaged = tmp_path / "damaged.onnx"
    damaged.write_bytes(b"not an onnx graph")
    raw = json.loads(tiny_onnx_config.read_text())
    raw["onnx"]["model_path"] = str(damaged)
    config = tmp_path / "damaged.json"
    config.write_text(json.dumps(raw))
    with pytest.raises(CheckpointCorruptError):
        OnnxEngine.from_config(config, verify_checksum=False)


def test_source_checkpoint_is_not_needed(tiny_onnx_config, tmp_path, make_image):
    raw = json.loads(tiny_onnx_config.read_text())
    raw["model"]["checkpoint_path"] = str(tmp_path / "absent.pth")
    config = tmp_path / "no_pth.json"
    config.write_text(json.dumps(raw))
    assert OnnxEngine.from_config(config).predict(InferenceRequest(make_image())).binary_mask.size
