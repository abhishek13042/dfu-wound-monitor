"""Synchronized image/mask augmentation for SPEC-02-03.

Every geometric parameter is sampled once and applied to both the image
(bilinear) and the mask (nearest), so the mask stays strictly binary and
aligned.  Photometric changes are applied to the image only, on the ``[0, 1]``
tensor before normalization.  All randomness comes from a ``torch.Generator``
seeded per sample and epoch, so a run is reproducible for a fixed seed and is
independent of DataLoader worker scheduling.
"""

from __future__ import annotations

from typing import Any

import torch
from torchvision.transforms import InterpolationMode
from torchvision.transforms.v2 import functional as TF

DEFAULT_AUGMENTATION: dict[str, Any] = {
    "horizontal_flip_prob": 0.5,
    "vertical_flip_prob": 0.5,
    "rotate90_prob": 0.5,
    "affine_prob": 0.7,
    "rotation_degrees": 30.0,
    "scale_range": [0.75, 1.25],
    "translate_fraction": 0.1,
    "shear_degrees": 5.0,
    "color_prob": 0.8,
    "brightness": 0.25,
    "contrast": 0.25,
    "saturation": 0.25,
    "hue": 0.04,
    "blur_prob": 0.15,
    "blur_sigma_range": [0.1, 1.5],
}


def _uniform(generator: torch.Generator, low: float, high: float) -> float:
    return float(low + (high - low) * torch.rand((), generator=generator).item())


def _chance(generator: torch.Generator, probability: float) -> bool:
    return probability > 0 and torch.rand((), generator=generator).item() < probability


def validate_augmentation_config(config: dict[str, Any]) -> dict[str, Any]:
    """Merge with defaults and reject out-of-range values."""

    unknown = set(config) - set(DEFAULT_AUGMENTATION) - {"validation_and_test"}
    if unknown:
        raise ValueError(f"Unknown augmentation keys: {sorted(unknown)}")
    merged = {**DEFAULT_AUGMENTATION, **{key: value for key, value in config.items() if key in DEFAULT_AUGMENTATION}}
    for key in ("horizontal_flip_prob", "vertical_flip_prob", "rotate90_prob", "affine_prob", "color_prob", "blur_prob"):
        if not 0.0 <= float(merged[key]) <= 1.0:
            raise ValueError(f"augmentation.{key} must be in [0, 1]")
    low, high = merged["scale_range"]
    if not 0 < low <= high:
        raise ValueError("augmentation.scale_range must satisfy 0 < low <= high")
    if not 0 <= merged["translate_fraction"] < 0.5:
        raise ValueError("augmentation.translate_fraction must be in [0, 0.5)")
    for key in ("rotation_degrees", "shear_degrees", "brightness", "contrast", "saturation"):
        if float(merged[key]) < 0:
            raise ValueError(f"augmentation.{key} must be non-negative")
    if not 0 <= merged["hue"] <= 0.5:
        raise ValueError("augmentation.hue must be in [0, 0.5]")
    sigma_low, sigma_high = merged["blur_sigma_range"]
    if not 0 < sigma_low <= sigma_high:
        raise ValueError("augmentation.blur_sigma_range must satisfy 0 < low <= high")
    return merged


class SegmentationAugmenter:
    """Callable ``(image01, mask, generator) -> (image01, mask)``."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = validate_augmentation_config(config or {})

    def __call__(
        self,
        image: torch.Tensor,
        mask: torch.Tensor,
        generator: torch.Generator,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        cfg = self.config
        if _chance(generator, cfg["horizontal_flip_prob"]):
            image, mask = TF.horizontal_flip(image), TF.horizontal_flip(mask)
        if _chance(generator, cfg["vertical_flip_prob"]):
            image, mask = TF.vertical_flip(image), TF.vertical_flip(mask)
        if _chance(generator, cfg["rotate90_prob"]):
            turns = int(torch.randint(1, 4, (), generator=generator).item())
            image = torch.rot90(image, turns, dims=(-2, -1))
            mask = torch.rot90(mask, turns, dims=(-2, -1))
        if _chance(generator, cfg["affine_prob"]):
            height, width = image.shape[-2:]
            angle = _uniform(generator, -cfg["rotation_degrees"], cfg["rotation_degrees"])
            scale = _uniform(generator, *cfg["scale_range"])
            max_dx, max_dy = cfg["translate_fraction"] * width, cfg["translate_fraction"] * height
            translate = [round(_uniform(generator, -max_dx, max_dx)), round(_uniform(generator, -max_dy, max_dy))]
            shear = [_uniform(generator, -cfg["shear_degrees"], cfg["shear_degrees"]), 0.0]
            image = TF.affine(image, angle=angle, translate=translate, scale=scale, shear=shear,
                              interpolation=InterpolationMode.BILINEAR, fill=0.0)
            mask = TF.affine(mask, angle=angle, translate=translate, scale=scale, shear=shear,
                             interpolation=InterpolationMode.NEAREST, fill=0.0)
        if _chance(generator, cfg["color_prob"]):
            # Random order is not needed for reproducibility; a fixed order is simpler.
            image = TF.adjust_brightness(image, _uniform(generator, 1 - cfg["brightness"], 1 + cfg["brightness"]))
            image = TF.adjust_contrast(image, _uniform(generator, 1 - cfg["contrast"], 1 + cfg["contrast"]))
            image = TF.adjust_saturation(image, _uniform(generator, 1 - cfg["saturation"], 1 + cfg["saturation"]))
            if cfg["hue"] > 0:
                image = TF.adjust_hue(image, _uniform(generator, -cfg["hue"], cfg["hue"]))
        if _chance(generator, cfg["blur_prob"]):
            sigma = _uniform(generator, *cfg["blur_sigma_range"])
            kernel = max(3, int(2 * round(3 * sigma) + 1))
            image = TF.gaussian_blur(image, kernel_size=[kernel, kernel], sigma=[sigma, sigma])
        return image.clamp(0.0, 1.0).contiguous(), (mask > 0.5).to(mask.dtype).contiguous()
