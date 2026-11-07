"""P07-S06 ONNX Runtime engine for the SPEC-02-03 segmentation model.

``OnnxEngine`` is a drop-in for ``InferenceEngine``: decoding, preprocessing,
threshold, small-component removal, warnings and provenance are inherited, so
only the forward pass differs (REQ-P07-S06-002).  Flip TTA runs the session
once per view and averages the inverted probabilities, as the PyTorch engine
does.

The ONNX file is pinned by the SHA-256 in the inference config's ``onnx``
block and is refused on mismatch, before ONNX Runtime parses it.

``create_engine`` picks the engine from ``DFU_INFERENCE_ENGINE`` (``pytorch``,
the default, or ``onnx``).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
import torch

from src.inference.engine import (
    DEFAULT_INFERENCE_CONFIG,
    PROJECT_ROOT,
    InferenceConfig,
    InferenceEngine,
    sha256_file,
)
from src.inference.errors import CheckpointChecksumError, CheckpointCorruptError, CheckpointMissingError, ConfigError
from src.inference.uncertainty import UncertaintyConfig

ENGINE_ENV = "DFU_INFERENCE_ENGINE"
ENGINES = ("pytorch", "onnx")
# The frozen PyTorch config stays unchanged; the export writes this copy with an ``onnx`` block.
DEFAULT_ONNX_CONFIG = PROJECT_ROOT / "configs" / "inference" / "spec_02_03_onnx_inference.json"
FLIP_VIEWS = ((), (-1,), (-2,), (-2, -1))


def onnx_settings(config: InferenceConfig) -> dict[str, Any]:
    block = config.raw.get("onnx")
    if not isinstance(block, dict):
        raise ConfigError(f"{config.path.name} has no 'onnx' block")
    for key in ("model_path", "model_sha256", "model_version", "opset"):
        if not block.get(key):
            raise ConfigError(f"Missing '{key}' in the onnx block of {config.path.name}")
    path = Path(block["model_path"])
    return {**block, "model_path": path if path.is_absolute() else PROJECT_ROOT / path,
            "model_sha256": str(block["model_sha256"]).lower()}


class OnnxEngine(InferenceEngine):
    def __init__(self, config: InferenceConfig, device: str | None = None, verify_checksum: bool = True,
                 uncertainty_config: UncertaintyConfig | None = None) -> None:
        if (device or config.device) != "cpu":
            raise ConfigError("OnnxEngine runs on the CPU execution provider only")
        self.onnx = onnx_settings(config)
        super().__init__(config, device="cpu", verify_checksum=verify_checksum, uncertainty_config=uncertainty_config)

    def _load_model(self, verify_checksum: bool):
        import onnxruntime as ort

        path = self.onnx["model_path"]
        if not path.is_file():
            raise CheckpointMissingError(f"ONNX model not found: {path}", {"model_path": str(path)})
        actual = sha256_file(path)
        if verify_checksum and actual != self.onnx["model_sha256"]:
            raise CheckpointChecksumError("ONNX model SHA-256 does not match the inference config",
                                          {"expected": self.onnx["model_sha256"], "actual": actual})
        options = ort.SessionOptions()
        if self.config.num_threads:
            options.intra_op_num_threads = int(self.config.num_threads)
        try:
            session = ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])
        except Exception as error:  # onnxruntime raises its own unexported types
            raise CheckpointCorruptError(f"ONNX model could not be loaded: {error}",
                                         {"model_path": str(path)}) from error
        self.input_name = session.get_inputs()[0].name
        info = {
            "checkpoint_path": str(path),
            "checkpoint_sha256": actual,
            "checksum_verified": verify_checksum,
            "source_checkpoint_sha256": self.onnx.get("source_checkpoint_sha256"),
            "onnx_opset": self.onnx["opset"],
            "onnxruntime_version": ort.__version__,
        }
        return session, info

    @property
    def model_version(self) -> str:
        return self.onnx["model_version"]

    def describe(self) -> dict[str, Any]:
        return {**super().describe(), "architecture": f"ResNetUNet/{self.config.encoder_name} (ONNX)", "runtime": "onnxruntime"}

    def _view_probabilities(self, batch: torch.Tensor) -> list[torch.Tensor]:
        array = batch.cpu().numpy().astype(np.float32)
        out = []
        for dims in FLIP_VIEWS if self.config.tta else FLIP_VIEWS[:1]:
            view = np.ascontiguousarray(np.flip(array, axis=dims)) if dims else array
            logits = self.model.run(None, {self.input_name: view})[0].astype(np.float32)
            probabilities = 1.0 / (1.0 + np.exp(-logits))
            out.append(torch.from_numpy(np.ascontiguousarray(np.flip(probabilities, axis=dims) if dims else probabilities)))
        return out


def engine_choice(value: str | None = None) -> str:
    choice = (value if value is not None else os.environ.get(ENGINE_ENV, "pytorch")).strip().lower() or "pytorch"
    if choice not in ENGINES:
        raise ConfigError(f"{ENGINE_ENV} must be one of {', '.join(ENGINES)}, got '{choice}'")
    return choice


def create_engine(path: str | Path = DEFAULT_INFERENCE_CONFIG, engine: str | None = None, **kwargs: Any) -> InferenceEngine:
    if engine_choice(engine) == "pytorch":
        return InferenceEngine(InferenceConfig.load(path), **kwargs)
    if Path(path) == DEFAULT_INFERENCE_CONFIG:
        path = DEFAULT_ONNX_CONFIG
    return OnnxEngine(InferenceConfig.load(path), **kwargs)
