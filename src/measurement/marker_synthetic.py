"""Synthetic scenes for the marker: a flat sheet with the marker and a known-length bar, seen by a pinhole camera.

Used by the tests and by ``scripts/evaluation/run_marker_validation.py --synthetic``. Every number it produces is
labelled synthetic; it checks the geometry code, not real cameras, lenses or skin.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

TEXTURE_PX_PER_MM = 10.0


@dataclass(frozen=True)
class Scene:
    image: np.ndarray            # RGB uint8
    bar_px: tuple[tuple[float, float], tuple[float, float]]   # bar end points in the image
    bar_mm: float
    true_px_per_mm: float        # at the sheet centre, fronto-parallel equivalent


def _sheet(dictionary: str, marker_id: int, marker_mm: float, sheet_mm: tuple[float, float],
           marker_at_mm: tuple[float, float], bar_from_mm: tuple[float, float], bar_mm: float) -> np.ndarray:
    scale = TEXTURE_PX_PER_MM
    width, height = int(sheet_mm[0] * scale), int(sheet_mm[1] * scale)
    sheet = np.full((height, width), 235, np.uint8)
    side = int(round(marker_mm * scale))
    marker = cv2.aruco.generateImageMarker(cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dictionary)),
                                           marker_id, side)
    x, y = int(marker_at_mm[0] * scale), int(marker_at_mm[1] * scale)
    sheet[y:y + side, x:x + side] = marker
    bx, by = bar_from_mm
    cv2.line(sheet, (int(bx * scale), int(by * scale)), (int((bx + bar_mm) * scale), int(by * scale)), 40,
             max(2, int(scale)))
    return sheet


def render_scene(*, px_per_mm: float, tilt_deg: float = 0.0, marker_id: int = 7, dictionary: str = "DICT_4X4_50",
                 marker_mm: float = 40.0, bar_mm: float = 60.0, image_size: tuple[int, int] = (640, 480),
                 offset_px: tuple[float, float] = (0.0, 0.0), noise: float = 0.0, seed: int = 0,
                 with_marker: bool = True, textured_background: bool = False) -> Scene:
    """Render the sheet tilted by ``tilt_deg`` about its horizontal axis.

    ``px_per_mm`` is the scale the sheet centre would have if it faced the camera; the camera sits at a fixed
    distance with a focal length chosen to give that scale. ``textured_background`` puts the sheet on a noisy,
    skin-toned surface with a dark red patch, so the scene passes the quality gate like a photo would.
    """
    sheet_mm = (marker_mm + bar_mm + 40.0, marker_mm + 30.0)
    marker_at = (10.0, 15.0)
    bar_from = (marker_mm + 25.0, 15.0 + marker_mm / 2)
    texture = _sheet(dictionary, marker_id, marker_mm, sheet_mm, marker_at, bar_from, bar_mm)
    if not with_marker:
        texture[int(marker_at[1] * TEXTURE_PX_PER_MM):, :int((marker_at[0] + marker_mm + 1) * TEXTURE_PX_PER_MM)] = 235
    distance_mm = 400.0
    focal = px_per_mm * distance_mm
    width, height = image_size
    cx, cy = width / 2 + offset_px[0], height / 2 + offset_px[1]
    angle = math.radians(tilt_deg)
    rotation = np.array([[1, 0, 0], [0, math.cos(angle), -math.sin(angle)], [0, math.sin(angle), math.cos(angle)]])
    camera = np.array([[focal, 0, cx], [0, focal, cy], [0, 0, 1]])
    # Sheet point (u, v) in mm, centred on the sheet, lies at R @ (u, v, 0) + (0, 0, distance).
    plane_to_image = camera @ np.column_stack([rotation[:, 0], rotation[:, 1], [0.0, 0.0, distance_mm]])
    texture_to_plane = np.array([[1 / TEXTURE_PX_PER_MM, 0, -sheet_mm[0] / 2],
                                 [0, 1 / TEXTURE_PX_PER_MM, -sheet_mm[1] / 2], [0, 0, 1]])
    homography = plane_to_image @ texture_to_plane
    image = cv2.warpPerspective(texture, homography, (width, height), flags=cv2.INTER_AREA, borderValue=180)
    rng = np.random.default_rng(seed)
    rgb = np.dstack([image] * 3).astype(np.float64)
    if textured_background:
        inside = cv2.warpPerspective(np.ones_like(texture), homography, (width, height), flags=cv2.INTER_NEAREST) > 0
        skin = np.full((height, width, 3), (170.0, 120.0, 100.0)) + rng.normal(0, 25, (height, width, 3))
        yy, xx = np.mgrid[:height, :width]
        skin[((yy - height * 0.8) ** 2 + (xx - width * 0.5) ** 2) < (height / 8) ** 2] = (150, 40, 40)
        rgb[~inside] = skin[~inside]
    if noise:
        rgb = rgb + rng.normal(0, noise, rgb.shape)
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)

    def project(point_mm: tuple[float, float]) -> tuple[float, float]:
        u, v = point_mm[0] - sheet_mm[0] / 2, point_mm[1] - sheet_mm[1] / 2
        x, y, w = plane_to_image @ np.array([u, v, 1.0])
        return float(x / w), float(y / w)

    bar = (project(bar_from), project((bar_from[0] + bar_mm, bar_from[1])))
    return Scene(rgb, bar, bar_mm, px_per_mm)
