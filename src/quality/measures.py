"""Deterministic image-quality measurements used by the P03-S02 gate.

All measures are computed on a working copy whose longest side is resized to
``analysis_size`` pixels.  Sharpness and other measures therefore do not depend
on the camera resolution.

* ``laplacian_variance`` - variance of the 4-neighbour Laplacian of luminance
  over content pixels (focus / motion blur).
* ``mean_luminance`` / ``luminance_std`` - exposure and contrast (0-255).
* ``dark_fraction`` / ``bright_fraction`` - share of content pixels below 16 or
  above 239 luminance (clipping).
* ``glare_fraction`` - share of content pixels that are near-white and
  unsaturated (specular reflection): min(R,G,B) >= 235 and
  max - min <= 25.
* ``content_fraction`` - share of the frame that is not uniform padding.
  FUSeg2021 images are zero-padded to 512x512, so exact-black border regions
  connected to the edge are excluded before the other measures are computed.
* ``entropy`` - Shannon entropy of the 64-bin luminance histogram over content
  pixels (bits); near-zero for blank or single-colour frames.
"""

from __future__ import annotations

import numpy as np
from PIL import Image
from scipy import ndimage

LAPLACIAN_KERNEL = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)


def _working_copy(image: Image.Image, analysis_size: int) -> np.ndarray:
    rgb = image.convert("RGB")
    scale = analysis_size / max(rgb.size)
    if scale < 1.0:
        rgb = rgb.resize((max(1, round(rgb.width * scale)), max(1, round(rgb.height * scale))),
                         resample=Image.Resampling.BILINEAR)
    return np.asarray(rgb, dtype=np.float32)


def _padding_mask(rgb: np.ndarray) -> np.ndarray:
    """Exact-black pixels connected to the frame border (letterbox padding)."""

    black = rgb.max(axis=2) <= 2
    if not black.any():
        return black
    labels, _ = ndimage.label(black)
    border = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    border = border[border > 0]
    return np.isin(labels, border)


def measure_quality(image: Image.Image, analysis_size: int = 512) -> dict[str, float]:
    rgb = _working_copy(image, analysis_size)
    luminance = rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    content = ~_padding_mask(rgb)
    content_fraction = float(content.mean())
    measures: dict[str, float] = {
        "width": float(image.width),
        "height": float(image.height),
        "content_fraction": content_fraction,
    }
    if content.sum() < 16:
        measures.update(laplacian_variance=0.0, mean_luminance=0.0, luminance_std=0.0, dark_fraction=1.0,
                        bright_fraction=0.0, glare_fraction=0.0, entropy=0.0)
        return measures

    laplacian = ndimage.convolve(luminance, LAPLACIAN_KERNEL, mode="nearest")
    # Ignore the Laplacian response on the padding edge itself.
    interior = ndimage.binary_erosion(content, iterations=2) if content_fraction < 1.0 else content
    if interior.sum() < 16:
        interior = content
    values = luminance[content]
    channel_min, channel_max = rgb.min(axis=2)[content], rgb.max(axis=2)[content]
    histogram, _ = np.histogram(values, bins=64, range=(0, 256))
    probabilities = histogram[histogram > 0] / values.size
    measures.update(
        laplacian_variance=float(laplacian[interior].var()),
        mean_luminance=float(values.mean()),
        luminance_std=float(values.std()),
        dark_fraction=float((values < 16).mean()),
        bright_fraction=float((values > 239).mean()),
        glare_fraction=float(((channel_min >= 235) & (channel_max - channel_min <= 25)).mean()),
        entropy=float(-(probabilities * np.log2(probabilities)).sum()),
    )
    return measures
