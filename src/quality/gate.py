"""P03-S02 image quality gate.

``QualityGate.evaluate`` returns ``ACCEPTED`` or ``REJECTED`` together with
every measured value, every reason code and the thresholds that were applied
(REQ-P03-S02-001/002).  An image that cannot be decoded is ``REJECTED`` with
``UNREADABLE``.  The gate never runs a model, so a quality rejection can never
be confused with a model or infrastructure failure (REQ-P03-S02-004).

Reason codes, in evaluation order:

========================  ==================================================
``UNREADABLE``            the bytes are not a decodable, allowed image
``TOO_SMALL``             shorter side < ``min_side_px``
``BAD_ASPECT_RATIO``      long/short side > ``max_aspect_ratio``
``INSUFFICIENT_CONTENT``  padding-free area or luminance entropy too low
                          (blank, single-colour or mostly letterboxed frame)
``BLURRY``                Laplacian variance < ``min_laplacian_variance``
``UNDEREXPOSED``          mean luminance too low or too many dark pixels
``OVEREXPOSED``           mean luminance too high or too many clipped pixels
``LOW_CONTRAST``          luminance std < ``min_luminance_std``
``GLARE``                 specular-glare fraction > ``max_glare_fraction``
========================  ==================================================

The content check is a technical proxy for field of view.  It does not verify
that a foot or wound is in the frame; that needs a learned model and a
separately approved specification.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.inference.errors import ConfigError, InputError
from src.preprocessing.decode import DecodedImage, ImageSource, decode_image
from src.quality.measures import measure_quality

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUALITY_CONFIG = PROJECT_ROOT / "configs" / "quality" / "quality_gate_v1.json"
ACCEPTED, REJECTED = "ACCEPTED", "REJECTED"
REASON_CODES = ("UNREADABLE", "TOO_SMALL", "BAD_ASPECT_RATIO", "INSUFFICIENT_CONTENT", "BLURRY",
                "UNDEREXPOSED", "OVEREXPOSED", "LOW_CONTRAST", "GLARE")
REQUIRED_CHECKS = (
    "min_side_px", "max_aspect_ratio", "min_laplacian_variance", "min_mean_luminance", "max_mean_luminance",
    "max_dark_fraction", "max_bright_fraction", "min_luminance_std", "max_glare_fraction",
    "min_content_fraction", "min_entropy_bits",
)


@dataclass(frozen=True)
class QualityConfig:
    path: str
    version: str
    sha256: str
    analysis_size: int
    checks: Dict[str, float]

    @classmethod
    def load(cls, path: Union[str, Path] = DEFAULT_QUALITY_CONFIG) -> "QualityConfig":
        path = Path(path)
        if not path.is_file():
            raise ConfigError(f"Quality config not found: {path}")
        data = path.read_bytes()
        try:
            raw = json.loads(data)
        except json.JSONDecodeError as error:
            raise ConfigError(f"Quality config is not valid JSON: {error}") from error
        checks = raw.get("checks") or {}
        missing = [key for key in REQUIRED_CHECKS if key not in checks]
        if missing:
            raise ConfigError(f"Quality config is missing checks: {missing}")
        for key in REQUIRED_CHECKS:
            value = checks[key]
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
                raise ConfigError(f"Quality check '{key}' must be a non-negative number, got {value!r}")
        if checks["min_mean_luminance"] >= checks["max_mean_luminance"]:
            raise ConfigError("min_mean_luminance must be below max_mean_luminance")
        version = raw.get("quality_config_version")
        if not version:
            raise ConfigError("quality_config_version is required")
        return cls(str(path), str(version), hashlib.sha256(data).hexdigest(), int(raw.get("analysis_size", 512)),
                   {key: float(checks[key]) for key in REQUIRED_CHECKS})

    def reference(self) -> Dict[str, Any]:
        return {"path": self.path, "version": self.version, "sha256": self.sha256}


@dataclass
class QualityResult:
    status: str
    reason_codes: List[str]
    measurements: Dict[str, float]
    thresholds: Dict[str, float]
    config_reference: Dict[str, Any]
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        return self.status == ACCEPTED

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class QualityGate:
    def __init__(self, config: Optional[QualityConfig] = None) -> None:
        self.config = config or QualityConfig.load()

    def evaluate(self, source: Union[ImageSource, DecodedImage], **decode_kwargs: Any) -> QualityResult:
        if not isinstance(source, DecodedImage):
            try:
                source = decode_image(source, **decode_kwargs)
            except InputError as error:
                return QualityResult(REJECTED, ["UNREADABLE"], {}, dict(self.config.checks),
                                     self.config.reference(), {"input_error": error.to_dict()})
        measures = measure_quality(source.image, self.config.analysis_size)
        status, reasons, rounded = self._decide(measures)
        return QualityResult(status, reasons, rounded, dict(self.config.checks), self.config.reference())

    def _decide(self, m: Dict[str, float]):
        c = self.config.checks
        reasons: List[str] = []
        short, long = min(m["width"], m["height"]), max(m["width"], m["height"])
        if short < c["min_side_px"]:
            reasons.append("TOO_SMALL")
        if long / max(short, 1.0) > c["max_aspect_ratio"]:
            reasons.append("BAD_ASPECT_RATIO")
        if m["content_fraction"] < c["min_content_fraction"] or m["entropy"] < c["min_entropy_bits"]:
            reasons.append("INSUFFICIENT_CONTENT")
        if m["laplacian_variance"] < c["min_laplacian_variance"]:
            reasons.append("BLURRY")
        if m["mean_luminance"] < c["min_mean_luminance"] or m["dark_fraction"] > c["max_dark_fraction"]:
            reasons.append("UNDEREXPOSED")
        if m["mean_luminance"] > c["max_mean_luminance"] or m["bright_fraction"] > c["max_bright_fraction"]:
            reasons.append("OVEREXPOSED")
        if m["luminance_std"] < c["min_luminance_std"]:
            reasons.append("LOW_CONTRAST")
        if m["glare_fraction"] > c["max_glare_fraction"]:
            reasons.append("GLARE")
        return (REJECTED if reasons else ACCEPTED), reasons, {k: round(v, 6) for k, v in m.items()}
