"""P03-S03: wound measurement engine (REQ-P03-S03-001..005)."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from src.measurement.engine import (
    PHYSICALLY_CALIBRATED,
    PIXEL_BASED,
    Calibration,
    MeasurementError,
    MeasurementResult,
    measure,
    perimeter_px,
)


def _square(side=20, shape=(64, 64), at=(10, 10)):
    mask = np.zeros(shape, dtype=np.uint8)
    mask[at[1]:at[1] + side, at[0]:at[0] + side] = 1
    return mask


def _disc(radius, shape=(256, 256)):
    yy, xx = np.mgrid[:shape[0], :shape[1]]
    cy, cx = shape[0] / 2, shape[1] / 2
    return (((yy - cy) ** 2 + (xx - cx) ** 2) <= radius ** 2).astype(np.uint8)


def _codes(result):
    return {warning["code"] for warning in result.warnings}


def test_square_geometry_is_exact():
    result = measure(_square())
    pixel = result.pixel
    assert result.measurement_basis == PIXEL_BASED and result.status == "MEASURED" and result.physical is None
    assert pixel["area_px"] == 400 and pixel["component_count"] == 1
    assert pixel["bbox"] == [10, 10, 29, 29] and pixel["bbox_width_px"] == pixel["bbox_height_px"] == 20
    assert pixel["extent"] == 1.0 and pixel["solidity"] == 1.0
    assert pixel["max_feret_px"] == pytest.approx(20 * math.sqrt(2), abs=1e-4)
    assert pixel["min_feret_px"] == pytest.approx(20, rel=1e-6)
    assert pixel["perimeter_px"] == pytest.approx(76, abs=1e-6)  # 4 * (side - 1) on pixel centres
    assert pixel["centroid_xy"] == [19.5, 19.5]
    assert pixel["equivalent_diameter_px"] == pytest.approx(math.sqrt(4 * 400 / math.pi), abs=1e-3)
    assert "UNCALIBRATED" in _codes(result)


@pytest.mark.parametrize("radius", [10, 25, 60])
def test_disc_perimeter_and_shape_within_documented_tolerance(radius):
    pixel = measure(_disc(radius)).pixel
    assert pixel["area_px"] == pytest.approx(math.pi * radius ** 2, rel=0.03)
    assert pixel["perimeter_px"] == pytest.approx(2 * math.pi * radius, rel=0.05)
    assert pixel["max_feret_px"] == pytest.approx(2 * radius + 1, rel=0.03)
    assert pixel["min_feret_px"] == pytest.approx(2 * radius + 1, rel=0.03)
    # The hull is built from pixel squares, so digitisation lowers solidity on small discs.
    assert pixel["circularity"] > 0.85 and pixel["solidity"] > 0.9


def test_rectangle_length_and_width():
    mask = np.zeros((100, 200), dtype=np.uint8)
    mask[40:50, 20:180] = 1
    pixel = measure(mask).pixel
    assert pixel["min_feret_px"] == pytest.approx(10, rel=1e-6)
    assert pixel["max_feret_px"] == pytest.approx(math.hypot(160, 10), abs=1e-4)
    assert pixel["circularity"] < 0.3


def test_hole_lowers_solidity_and_adds_perimeter():
    solid = _disc(30)
    holed = solid.copy()
    holed[118:138, 118:138] = 0
    a, b = measure(solid).pixel, measure(holed).pixel
    assert b["area_px"] == a["area_px"] - 400
    assert b["perimeter_px"] > a["perimeter_px"] + 60
    assert b["solidity"] < a["solidity"]


def test_calibrated_measurements_convert_lengths_and_areas():
    calibration = Calibration(pixels_per_mm=4.0, method="USER_ENTERED", source="test ruler")
    result = measure(_square(side=40, shape=(80, 80), at=(20, 20)), calibration=calibration)
    assert result.measurement_basis == PHYSICALLY_CALIBRATED
    assert result.physical["area_mm2"] == pytest.approx(1600 / 16)
    assert result.physical["bbox_width_mm"] == pytest.approx(10)
    assert result.physical["perimeter_mm"] == pytest.approx(result.pixel["perimeter_px"] / 4)
    assert result.components[0]["physical"]["area_mm2"] == pytest.approx(100)
    assert result.calibration["method"] == "USER_ENTERED"
    assert "UNCALIBRATED" not in _codes(result)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"pixels_per_mm": 0, "method": "USER_ENTERED"},
        {"pixels_per_mm": -2, "method": "USER_ENTERED"},
        {"pixels_per_mm": float("nan"), "method": "USER_ENTERED"},
        {"pixels_per_mm": float("inf"), "method": "USER_ENTERED"},
        {"pixels_per_mm": True, "method": "USER_ENTERED"},
        {"pixels_per_mm": 5, "method": "GUESSED"},
        {"pixels_per_mm": 5, "method": "REFERENCE_MARKER", "uncertainty_pct": 150},
    ],
)
def test_invalid_calibration_is_refused(kwargs):
    with pytest.raises(MeasurementError) as info:
        Calibration(**kwargs)
    assert info.value.code == "CALIBRATION_INVALID"


def test_empty_mask_is_explicit_not_zero_geometry():
    result = measure(np.zeros((32, 32), dtype=np.uint8))
    assert result.status == "EMPTY" and result.pixel["area_px"] == 0 and result.components == []
    assert "EMPTY_MASK" in _codes(result)


def test_multiple_components_are_listed_largest_first():
    mask = _square(side=20, shape=(80, 80), at=(5, 5))
    mask[50:60, 50:60] = 1
    result = measure(mask)
    assert result.pixel["component_count"] == 2 and result.pixel["area_px"] == 500
    assert [c["area_px"] for c in result.components] == [400, 100]
    assert [c["rank"] for c in result.components] == [1, 2]
    assert "MULTIPLE_COMPONENTS" in _codes(result)


def test_diagonal_pixels_are_one_component():
    mask = np.zeros((10, 10), dtype=np.uint8)
    mask[2, 2] = mask[3, 3] = 1
    assert measure(mask).pixel["component_count"] == 1


def test_border_small_and_low_confidence_warnings():
    mask = _square(side=8, shape=(32, 32), at=(0, 0))
    probability = np.where(mask == 1, 0.55, 0.05).astype(np.float32)
    result = measure(mask, probability_mask=probability)
    assert {"TOUCHES_IMAGE_BORDER", "SMALL_REGION", "LOW_CONFIDENCE"} <= _codes(result)
    assert result.confidence["mean_probability_in_mask"] == pytest.approx(0.55, abs=1e-4)
    assert result.confidence["uncertain_fraction"] == 1.0


def test_confident_mask_has_no_confidence_warning():
    mask = _square(side=20, shape=(64, 64), at=(20, 20))
    result = measure(mask, probability_mask=np.where(mask == 1, 0.95, 0.0).astype(np.float32))
    assert "LOW_CONFIDENCE" not in _codes(result) and "CONFIDENCE_NOT_ASSESSED" not in _codes(result)
    assert "CONFIDENCE_NOT_ASSESSED" in _codes(measure(mask))


def test_bool_mask_is_accepted():
    assert measure(_square().astype(bool)).pixel["area_px"] == 400


@pytest.mark.parametrize(
    "mask",
    [
        [[0, 1], [1, 0]],
        np.zeros((4, 4, 3), dtype=np.uint8),
        np.zeros((0, 5), dtype=np.uint8),
        np.array([[0, 2], [1, 0]], dtype=np.uint8),
        np.array([[0.0, np.nan], [1.0, 0.0]]),
        np.array([["a", "b"]]),
    ],
)
def test_malformed_masks_raise(mask):
    with pytest.raises(MeasurementError) as info:
        measure(mask)
    assert info.value.code == "MASK_MALFORMED"


@pytest.mark.parametrize(
    "probability",
    [np.zeros((5, 5), dtype=np.float32), np.full((64, 64), 1.5, dtype=np.float32), [[0.5]]],
)
def test_malformed_probability_maps_raise(probability):
    with pytest.raises(MeasurementError) as info:
        measure(_square(), probability_mask=probability)
    assert info.value.code == "PROBABILITY_MALFORMED"


def test_result_serialises_and_round_trips_with_provenance():
    result = measure(_square(), calibration=Calibration(2.0, "REFERENCE_MARKER", "marker-A", 3.0),
                     provenance={"model": {"model_version": "m1"}})
    payload = json.loads(json.dumps(result.to_dict()))
    assert MeasurementResult.from_dict(payload).to_dict() == result.to_dict()
    assert payload["provenance"]["model"]["model_version"] == "m1"
    assert payload["provenance"]["measurement"]["engine_version"].startswith("p03-s03")
    assert "Not a clinical measurement" in payload["limitation"]


def test_measurement_is_deterministic():
    mask = _disc(17, (64, 64))
    assert measure(mask).to_dict() == measure(mask).to_dict()


def test_perimeter_of_single_pixel_and_line():
    single = np.zeros((5, 5), dtype=np.uint8)
    single[2, 2] = 1
    assert perimeter_px(single) == 0.0
    line = np.zeros((5, 12), dtype=np.uint8)
    line[2, 1:11] = 1
    # Benkrid/scikit-image convention: a one-pixel-wide line counts its inner
    # border pixels once (length - 2), so thin structures are under-measured.
    assert perimeter_px(line) == pytest.approx(8.0)
