"""REQ-P09-S02-002: a summary of how much the flip-TTA views disagree.

Each flip view is the model's probability map for the image seen mirrored, flipped back. Where the views disagree,
the model's answer depends on orientation, which is weak evidence that it is less certain there. The summary is the
mean absolute difference over all view pairs, taken inside the predicted region and a narrow band around it; an empty
prediction is summarised over the whole image and flagged. It is model uncertainty, never a probability that the
result is correct, and it never changes the mask or the measurements.

Whether the number is shown to users is decided by the study (``scripts/evaluation/run_uncertainty_study.py``) and
recorded as ``summary_shown`` in ``configs/inference/uncertainty_v1.json``.
"""

from __future__ import annotations

import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.inference.errors import ConfigError

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_UNCERTAINTY_CONFIG = ROOT / "configs" / "inference" / "uncertainty_v1.json"
METHOD = "flip_tta_v1"
MASK_AND_BAND, WHOLE_IMAGE = "MASK_AND_BAND", "WHOLE_IMAGE"


@dataclass(frozen=True)
class UncertaintyConfig:
    version: str
    band_px: int
    summary_shown: bool
    path: Path

    @classmethod
    def load(cls, path: str | Path = DEFAULT_UNCERTAINTY_CONFIG) -> UncertaintyConfig:
        path = Path(path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            config = cls(str(raw["version"]), int(raw["band_px"]), bool(raw["summary_shown"]), path)
        except (OSError, KeyError, TypeError, ValueError) as error:
            raise ConfigError(f"Cannot read uncertainty config {path}: {error}") from error
        if raw.get("method") != METHOD or config.band_px < 0:
            raise ConfigError(f"Uncertainty config {path} needs method {METHOD} and band_px >= 0")
        return config


def tta_disagreement(views: np.ndarray, mask: np.ndarray, band_px: int) -> dict[str, Any] | None:
    """Summarise ``views`` (V, H, W probabilities) over ``mask`` (H, W) widened by ``band_px``.

    Returns None when there is only one view (TTA off), because there is nothing to compare.
    """

    views = np.asarray(views, dtype=np.float32)
    if views.ndim != 3 or views.shape[1:] != mask.shape:
        raise ValueError(f"views {views.shape} do not match mask {mask.shape}")
    if views.shape[0] < 2:
        return None
    mask = np.asarray(mask, dtype=bool)
    empty = not mask.any()
    if empty:
        region = np.ones_like(mask)
    elif band_px:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * band_px + 1, 2 * band_px + 1))
        region = cv2.dilate(mask.astype(np.uint8), kernel).astype(bool)
    else:
        region = mask
    pairs = list(itertools.combinations(range(views.shape[0]), 2))
    value = float(np.mean([np.abs(views[i][region] - views[j][region]).mean() for i, j in pairs]))
    return {"tta_disagreement": round(value, 6), "method": METHOD, "views": int(views.shape[0]),
            "region": WHOLE_IMAGE if empty else MASK_AND_BAND, "band_px": band_px,
            "region_pixels": int(region.sum()), "empty_mask": empty}
