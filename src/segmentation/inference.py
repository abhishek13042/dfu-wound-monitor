"""Inference, post-processing, threshold tuning and native-resolution evaluation.

SPEC-02-03 evaluation contract:

* Probabilities are predicted at the network input size, then bilinearly
  resized to each image's **native** resolution.  Metrics are computed against
  the original, un-resized ground-truth mask, so the score is not inflated or
  deflated by mask resampling.
* Optional test-time augmentation (TTA) averages probabilities over the
  identity, horizontal, vertical and combined flips.
* Post-processing removes connected components smaller than
  ``min_component_area`` native pixels.
* The probability threshold and minimum component area are chosen on the
  internal validation split only, then frozen before the held-out test split
  is evaluated once.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from scipy import ndimage

from src.segmentation.dataset import preprocess_image
from src.segmentation.metrics import aggregate_metrics, compute_binary_segmentation_metrics, compute_hd95

DEFAULT_THRESHOLD_GRID = tuple(round(value, 2) for value in np.arange(0.30, 0.71, 0.05))
DEFAULT_MIN_AREA_GRID = (0, 64, 128, 256, 512)


def predict_logits_tta(model: nn.Module, images: torch.Tensor, tta: bool = True) -> torch.Tensor:
    """Return mean probabilities ``(B,1,H,W)``; flips are inverted before averaging."""

    probabilities = torch.sigmoid(model(images).float())
    if not tta:
        return probabilities
    views = 1
    for dims in ((-1,), (-2,), (-2, -1)):
        flipped = torch.flip(images, dims=dims)
        probabilities = probabilities + torch.flip(torch.sigmoid(model(flipped).float()), dims=dims)
        views += 1
    return probabilities / views


def load_binary_mask(path: Path, target_size: tuple[int, int] | None = None, threshold: int = 128) -> np.ndarray:
    """Load a mask as ``uint8`` {0,1}.

    ``target_size`` is ``(width, height)``.  A mask whose size differs from its
    image is resized with nearest-neighbour interpolation.  This is used only
    for external datasets whose masks were distributed at a different size
    (LowerLimbFeetWound V3) and is recorded per sample by the caller.
    """

    with Image.open(path) as mask_file:
        mask = mask_file.convert("L")
        if target_size is not None and mask.size != tuple(target_size):
            mask = mask.resize(tuple(target_size), resample=Image.Resampling.NEAREST)
        return (np.asarray(mask, dtype=np.uint8) >= threshold).astype(np.uint8)


def remove_small_components(binary_mask: np.ndarray, min_component_area: int) -> np.ndarray:
    """Drop 8-connected foreground components smaller than ``min_component_area``."""

    if min_component_area <= 0 or not binary_mask.any():
        return binary_mask
    labels, count = ndimage.label(binary_mask, structure=np.ones((3, 3), dtype=np.uint8))
    if count == 0:
        return binary_mask
    areas = np.bincount(labels.ravel())
    keep = areas >= min_component_area
    keep[0] = False
    return keep[labels].astype(binary_mask.dtype)


@torch.no_grad()
def predict_native_probabilities(
    model: nn.Module,
    image_paths: Sequence[Path],
    input_height: int,
    input_width: int,
    normalize_mean: list[float],
    normalize_std: list[float],
    device: torch.device,
    tta: bool = True,
    use_amp: bool = False,
    batch_size: int = 4,
) -> list[np.ndarray]:
    """Predict probability maps at each image's native resolution (``float16``)."""

    model.eval()
    outputs: list[np.ndarray] = []
    for start in range(0, len(image_paths), batch_size):
        chunk = image_paths[start:start + batch_size]
        native_sizes: list[tuple[int, int]] = []
        tensors = []
        for path in chunk:
            with Image.open(path) as image_file:
                image = image_file.convert("RGB")
                native_sizes.append((image.height, image.width))
                tensors.append(preprocess_image(image, input_height, input_width, normalize_mean, normalize_std))
        batch = torch.stack(tensors).to(device)
        with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=use_amp and device.type == "cuda"):
            probabilities = predict_logits_tta(model, batch, tta=tta)
        for index, (height, width) in enumerate(native_sizes):
            native = F.interpolate(
                probabilities[index:index + 1].float(), size=(height, width), mode="bilinear", align_corners=False
            )
            outputs.append(native[0, 0].clamp(0, 1).cpu().numpy().astype(np.float16))
    return outputs


def score_predictions(
    sample_ids: Sequence[str],
    probabilities: Sequence[np.ndarray],
    ground_truths: Sequence[np.ndarray],
    threshold: float,
    min_component_area: int = 0,
    include_hd95: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Binarize, post-process and score native-resolution predictions."""

    if not (len(sample_ids) == len(probabilities) == len(ground_truths)):
        raise ValueError("sample_ids, probabilities and ground_truths must have equal length")
    per_sample: list[dict[str, Any]] = []
    for sample_id, probability, ground_truth in zip(sample_ids, probabilities, ground_truths):
        if probability.shape != ground_truth.shape:
            raise ValueError(f"{sample_id}: prediction {probability.shape} vs mask {ground_truth.shape}")
        prediction = (probability.astype(np.float32) >= threshold).astype(np.uint8)
        prediction = remove_small_components(prediction, min_component_area)
        metrics = compute_binary_segmentation_metrics(prediction, ground_truth)
        result = {
            "sample_id": sample_id,
            "prediction_threshold": threshold,
            "min_component_area": min_component_area,
            "native_height": int(ground_truth.shape[0]),
            "native_width": int(ground_truth.shape[1]),
            "wound_area_ratio_predicted": float(prediction.mean()),
            "wound_area_ratio_ground_truth": float(ground_truth.mean()),
            **metrics,
        }
        if include_hd95:
            result["hd95"] = compute_hd95(prediction, ground_truth)
            result["hd95_undefined"] = result["hd95"] is None
        per_sample.append(result)
    return aggregate_metrics(per_sample), per_sample


def tune_postprocessing(
    sample_ids: Sequence[str],
    probabilities: Sequence[np.ndarray],
    ground_truths: Sequence[np.ndarray],
    thresholds: Iterable[float] = DEFAULT_THRESHOLD_GRID,
    min_areas: Iterable[int] = DEFAULT_MIN_AREA_GRID,
    selection_metric: str = "mean_dice",
) -> dict[str, Any]:
    """Grid-search threshold and minimum component area on validation data.

    Ties are broken toward threshold 0.5 and the smaller area, i.e. toward
    the least post-processing.
    """

    grid: list[dict[str, Any]] = []
    for threshold in thresholds:
        for min_area in min_areas:
            aggregate, _ = score_predictions(sample_ids, probabilities, ground_truths, float(threshold), int(min_area))
            grid.append({
                "threshold": float(threshold),
                "min_component_area": int(min_area),
                selection_metric: float(aggregate[selection_metric]),
                "pooled_dice": float(aggregate.get("pooled_dice", float("nan"))),
            })
    best = max(grid, key=lambda row: (round(row[selection_metric], 6), -abs(row["threshold"] - 0.5), -row["min_component_area"]))
    return {"selection_metric": selection_metric, "best": best, "grid": grid}
