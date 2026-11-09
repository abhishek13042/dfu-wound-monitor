"""PNG encoding of masks, probability maps and overlays for the API."""

from __future__ import annotations

import io

import numpy as np
from PIL import Image
from scipy import ndimage


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=False)
    return buffer.getvalue()


def mask_png(mask: np.ndarray) -> bytes:
    """Binary mask as an 8-bit PNG with values {0, 255}."""

    return _png(Image.fromarray(mask.astype(np.uint8) * 255))


def probability_png(probability: np.ndarray) -> bytes:
    """Probability map quantised to 16 bits (step 1/65535)."""

    return _png(Image.fromarray(np.round(probability * 65535).astype(np.uint16)))


def decode_mask_png(data: bytes) -> np.ndarray:
    return (np.asarray(Image.open(io.BytesIO(data))) > 127).astype(np.uint8)


def overlay_png(image: Image.Image, mask: np.ndarray, max_side: int | None = 1024) -> bytes:
    """Red translucent fill plus a yellow outline of the mask over the image."""

    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    region = mask.astype(bool)
    edge = region & ~ndimage.binary_erosion(region, iterations=max(1, min(rgb.shape[:2]) // 300))
    out = rgb.copy()
    out[region] = 0.55 * out[region] + 0.45 * np.array([220, 30, 30], dtype=np.float32)
    out[edge] = (255, 220, 0)
    result = Image.fromarray(out.clip(0, 255).astype(np.uint8))
    if max_side and max(result.size) > max_side:
        scale = max_side / max(result.size)
        result = result.resize((round(result.width * scale), round(result.height * scale)), Image.Resampling.LANCZOS)
    return _png(result)
