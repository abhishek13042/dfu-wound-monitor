"""P03-S01 inference engine for the SPEC-02-03 segmentation model.

``InferenceEngine`` binds one model artifact to one inference configuration:

* Preprocessing (input size, normalisation) and architecture are read from the
  **training** config that produced the checkpoint.  The engine accepts no
  preprocessing overrides (REQ-P03-S01-001).
* The checkpoint is verified against the SHA-256 recorded in the inference
  config before it is deserialised, and is loaded with ``weights_only=True``.
* ``predict`` returns an ``InferenceResult`` with the native-resolution
  probability map, the post-processed binary mask, full provenance and
  warnings, or raises a typed ``InferenceError`` (REQ-P03-S01-002/003).
* Inference runs in eval mode with no randomness; see the config's
  ``determinism_policy`` (REQ-P03-S01-004).
"""

from __future__ import annotations

import hashlib
import json
import platform
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import torch
import torch.nn.functional as F
from torch.torch_version import TorchVersion

from src.inference.errors import (
    CheckpointChecksumError,
    CheckpointCorruptError,
    CheckpointIncompatibleError,
    CheckpointMissingError,
    ConfigError,
    InputError,
    ModelExecutionError,
)
from src.preprocessing.decode import DecodedImage, ImageSource, decode_image
from src.segmentation.dataset import preprocess_image
from src.segmentation.inference import predict_logits_tta, remove_small_components
from src.segmentation.resnet_unet import ResNetUNet

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INFERENCE_CONFIG = PROJECT_ROOT / "configs" / "inference" / "spec_02_03_inference.json"
ENGINE_VERSION = "p03-s01-1.0"


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require(mapping: Dict[str, Any], key: str, where: str) -> Any:
    if key not in mapping or mapping[key] is None:
        raise ConfigError(f"Missing '{key}' in {where}")
    return mapping[key]


@dataclass(frozen=True)
class InferenceConfig:
    path: Path
    sha256: str
    version: str
    model_version: str
    experiment_id: str
    checkpoint_path: Path
    checkpoint_sha256: str
    training_config_path: Path
    training_config_sha256: str
    encoder_name: str
    decoder_channels: tuple
    input_height: int
    input_width: int
    normalize_mean: tuple
    normalize_std: tuple
    threshold: float
    min_component_area: int
    tta: bool
    allowed_formats: tuple
    max_pixels: int
    apply_exif_orientation: bool
    device: str
    num_threads: Optional[int]
    determinism_policy: str
    raw: Dict[str, Any] = field(repr=False, compare=False, default_factory=dict)

    @classmethod
    def load(cls, path: Union[str, Path] = DEFAULT_INFERENCE_CONFIG, base_dir: Path = PROJECT_ROOT) -> "InferenceConfig":
        path = Path(path)
        if not path.is_file():
            raise ConfigError(f"Inference config not found: {path}")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ConfigError(f"Inference config is not valid JSON: {error}") from error

        def resolve(value: str) -> Path:
            candidate = Path(value)
            return candidate if candidate.is_absolute() else base_dir / candidate

        model = _require(raw, "model", path.name)
        post = _require(raw, "postprocessing", path.name)
        inputs = raw.get("input", {})
        runtime = raw.get("runtime", {})
        training_path = resolve(_require(model, "training_config_path", "model"))
        if not training_path.is_file():
            raise ConfigError(f"Training config not found: {training_path}")
        training = json.loads(training_path.read_text(encoding="utf-8"))
        prep = _require(training, "preprocessing", training_path.name)
        model_cfg = _require(training, "model", training_path.name)

        threshold = float(_require(post, "threshold", "postprocessing"))
        min_area = int(_require(post, "min_component_area", "postprocessing"))
        if not 0.0 < threshold < 1.0:
            raise ConfigError(f"threshold must be in (0,1), got {threshold}")
        if min_area < 0:
            raise ConfigError(f"min_component_area must be >= 0, got {min_area}")
        height, width = int(_require(prep, "input_height", "preprocessing")), int(_require(prep, "input_width", "preprocessing"))
        if height <= 0 or width <= 0 or height % 32 or width % 32:
            raise ConfigError(f"Input size {height}x{width} must be positive multiples of 32")
        checksum = str(_require(model, "checkpoint_sha256", "model")).lower()
        if len(checksum) != 64:
            raise ConfigError("checkpoint_sha256 must be a 64-character hex digest")

        return cls(
            path=path,
            sha256=sha256_file(path),
            version=str(_require(raw, "inference_config_version", path.name)),
            model_version=str(_require(model, "model_version", "model")),
            experiment_id=str(model.get("experiment_id", "")),
            checkpoint_path=resolve(_require(model, "checkpoint_path", "model")),
            checkpoint_sha256=checksum,
            training_config_path=training_path,
            training_config_sha256=sha256_file(training_path),
            encoder_name=str(_require(model_cfg, "encoder_name", "training model")),
            decoder_channels=tuple(int(c) for c in model_cfg.get("decoder_channels", (256, 128, 64, 32, 16))),
            input_height=height,
            input_width=width,
            normalize_mean=tuple(float(v) for v in _require(prep, "normalize_mean", "preprocessing")),
            normalize_std=tuple(float(v) for v in _require(prep, "normalize_std", "preprocessing")),
            threshold=threshold,
            min_component_area=min_area,
            tta=bool(post.get("tta", True)),
            allowed_formats=tuple(inputs.get("allowed_formats", ("PNG", "JPEG", "BMP", "TIFF", "WEBP"))),
            max_pixels=int(inputs.get("max_pixels", 50_000_000)),
            apply_exif_orientation=bool(inputs.get("apply_exif_orientation", True)),
            device=str(runtime.get("device", "cpu")),
            num_threads=runtime.get("num_threads"),
            determinism_policy=str(runtime.get("determinism_policy", "")),
            raw=raw,
        )

    def preprocessing(self) -> Dict[str, Any]:
        return {
            "source": str(self.training_config_path.relative_to(PROJECT_ROOT)) if self.training_config_path.is_relative_to(PROJECT_ROOT) else str(self.training_config_path),
            "input_height": self.input_height,
            "input_width": self.input_width,
            "resize": "bilinear",
            "normalize_mean": list(self.normalize_mean),
            "normalize_std": list(self.normalize_std),
        }


@dataclass(frozen=True)
class InferenceRequest:
    """One image to segment.

    The model artifact and configuration are bound to the engine that handles
    the request.  ``threshold`` may override the frozen value; the override is
    recorded as a warning and in provenance.
    """

    image: Union[ImageSource, DecodedImage]
    threshold: Optional[float] = None
    request_id: Optional[str] = None


@dataclass
class InferenceResult:
    probability_mask: np.ndarray      # float32 (H, W) at native resolution, values in [0, 1]
    binary_mask: np.ndarray           # uint8 (H, W) in {0, 1}, after post-processing
    provenance: Dict[str, Any]
    warnings: List[Dict[str, Any]]

    def summary(self) -> Dict[str, Any]:
        return {
            "foreground_pixels": int(self.binary_mask.sum()),
            "height": int(self.binary_mask.shape[0]),
            "width": int(self.binary_mask.shape[1]),
            "warnings": self.warnings,
            "provenance": self.provenance,
        }


class InferenceEngine:
    def __init__(self, config: InferenceConfig, device: Optional[str] = None, verify_checksum: bool = True) -> None:
        self.config = config
        self.device = torch.device(device or config.device)
        if self.device.type == "cuda" and not torch.cuda.is_available():
            raise ConfigError("Config requests CUDA but no CUDA device is available")
        if config.num_threads:
            torch.set_num_threads(int(config.num_threads))
        self.model, self.checkpoint_info = self._load_model(verify_checksum)

    @classmethod
    def from_config(cls, path: Union[str, Path] = DEFAULT_INFERENCE_CONFIG, **kwargs: Any) -> "InferenceEngine":
        return cls(InferenceConfig.load(path), **kwargs)

    def _load_model(self, verify_checksum: bool):
        path = self.config.checkpoint_path
        if not path.is_file():
            raise CheckpointMissingError(f"Checkpoint not found: {path}", {"checkpoint_path": str(path)})
        actual = sha256_file(path)
        if verify_checksum and actual != self.config.checkpoint_sha256:
            raise CheckpointChecksumError(
                "Checkpoint SHA-256 does not match the inference config",
                {"expected": self.config.checkpoint_sha256, "actual": actual},
            )
        try:
            with torch.serialization.safe_globals([TorchVersion]):
                checkpoint = torch.load(path, map_location="cpu", weights_only=True)
        except Exception as safe_error:  # torch raises many unrelated types for a damaged file
            # Training metadata stores numpy scalars, which the restricted unpickler
            # refuses.  A full unpickle is allowed only for the exact file whose
            # SHA-256 is pinned in the inference config.
            if not verify_checksum:
                raise CheckpointCorruptError(f"Checkpoint could not be read safely: {safe_error}",
                                             {"checkpoint_path": str(path)}) from safe_error
            try:
                checkpoint = torch.load(path, map_location="cpu", weights_only=False)
            except Exception as error:
                raise CheckpointCorruptError(f"Checkpoint could not be read: {error}",
                                             {"checkpoint_path": str(path)}) from error
        if not isinstance(checkpoint, dict) or "model_state_dict" not in checkpoint:
            raise CheckpointIncompatibleError("Checkpoint has no 'model_state_dict'")
        state = {key.removeprefix("module."): value for key, value in checkpoint["model_state_dict"].items() if key != "n_averaged"}
        model = ResNetUNet(self.config.encoder_name, pretrained=False, num_classes=1,
                           decoder_channels=self.config.decoder_channels)
        try:
            model.load_state_dict(state, strict=True)
        except RuntimeError as error:
            raise CheckpointIncompatibleError(
                f"Checkpoint does not match {self.config.encoder_name} U-Net: {str(error)[:500]}"
            ) from error
        model.to(self.device).eval()
        info = {
            "checkpoint_path": str(path),
            "checkpoint_sha256": actual,
            "checksum_verified": verify_checksum,
            "checkpoint_epoch": checkpoint.get("epoch"),
            "checkpoint_val_dice": checkpoint.get("best_metric_value", checkpoint.get("val_dice")),
        }
        return model, info

    def describe(self) -> Dict[str, Any]:
        cfg = self.config
        return {
            "model_version": cfg.model_version,
            "experiment_id": cfg.experiment_id,
            "architecture": f"ResNetUNet/{cfg.encoder_name}",
            **self.checkpoint_info,
            "inference_config": str(cfg.path),
            "inference_config_version": cfg.version,
            "inference_config_sha256": cfg.sha256,
            "training_config": str(cfg.training_config_path),
            "training_config_sha256": cfg.training_config_sha256,
            "preprocessing": cfg.preprocessing(),
            "postprocessing": {"threshold": cfg.threshold, "min_component_area": cfg.min_component_area, "tta": cfg.tta},
            "device": str(self.device),
            "determinism_policy": cfg.determinism_policy,
            "engine_version": ENGINE_VERSION,
        }

    def decode(self, source: Union[ImageSource, DecodedImage]) -> DecodedImage:
        if isinstance(source, DecodedImage):
            return source
        return decode_image(source, self.config.allowed_formats, self.config.max_pixels,
                            self.config.apply_exif_orientation)

    @torch.inference_mode()
    def predict(self, request: InferenceRequest) -> InferenceResult:
        cfg = self.config
        started = time.perf_counter()
        decoded = self.decode(request.image)
        warnings: List[Dict[str, Any]] = []
        threshold = cfg.threshold
        if request.threshold is not None:
            if not 0.0 < float(request.threshold) < 1.0:
                raise InputError(f"threshold must be in (0,1), got {request.threshold}")
            threshold = float(request.threshold)
            if threshold != cfg.threshold:
                warnings.append({"code": "THRESHOLD_OVERRIDE",
                                 "message": f"Threshold {threshold} differs from the frozen {cfg.threshold}"})
        if decoded.exif_orientation_applied:
            warnings.append({"code": "EXIF_ORIENTATION_APPLIED",
                             "message": "Image was rotated according to its EXIF orientation before inference"})

        try:
            tensor = preprocess_image(decoded.image, cfg.input_height, cfg.input_width,
                                      list(cfg.normalize_mean), list(cfg.normalize_std))
            batch = tensor.unsqueeze(0).to(self.device)
            probabilities = predict_logits_tta(self.model, batch, tta=cfg.tta)
            native = F.interpolate(probabilities.float(), size=(decoded.height, decoded.width),
                                   mode="bilinear", align_corners=False)
            probability = native[0, 0].clamp(0, 1).cpu().numpy().astype(np.float32)
        except Exception as error:
            raise ModelExecutionError(f"Model forward pass failed: {error}") from error
        if not np.isfinite(probability).all():
            raise ModelExecutionError("Model produced non-finite probabilities")

        raw_binary = (probability >= threshold).astype(np.uint8)
        binary = remove_small_components(raw_binary, cfg.min_component_area)
        removed = int(raw_binary.sum() - binary.sum())
        if removed:
            warnings.append({"code": "SMALL_COMPONENTS_REMOVED",
                             "message": f"{removed} px in components below {cfg.min_component_area} px were removed",
                             "removed_pixels": removed})
        if not binary.any():
            warnings.append({"code": "EMPTY_PREDICTION", "message": "No wound region was segmented"})

        provenance = {
            "request_id": request.request_id,
            "input": {
                "reference": decoded.source_reference,
                "sha256": decoded.sha256,
                "format": decoded.source_format,
                "width": decoded.width,
                "height": decoded.height,
                "exif_orientation_applied": decoded.exif_orientation_applied,
            },
            "model": {key: value for key, value in self.describe().items()
                      if key not in ("preprocessing", "postprocessing", "determinism_policy")},
            "preprocessing": cfg.preprocessing(),
            "postprocessing": {"threshold": threshold, "frozen_threshold": cfg.threshold,
                               "min_component_area": cfg.min_component_area, "tta": cfg.tta},
            "execution": {
                "device": str(self.device),
                "torch_version": torch.__version__,
                "python_version": platform.python_version(),
                "num_threads": torch.get_num_threads(),
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        return InferenceResult(probability, binary, provenance, warnings)
