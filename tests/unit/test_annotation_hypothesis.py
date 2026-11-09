"""P09-S04: the two measures behind the annotation-protocol tests."""

import numpy as np
import pytest

from scripts.evaluation.run_annotation_hypothesis import colour_test, solidity


def test_solidity_of_a_square_is_one_and_of_an_l_shape_is_lower():
    square = np.zeros((40, 40), bool)
    square[10:30, 10:30] = True
    l_shape = square.copy()
    l_shape[10:20, 20:30] = False

    assert solidity(square) == pytest.approx(1.0, abs=0.01)
    assert solidity(l_shape) < 0.85
    assert solidity(np.zeros((10, 10), bool)) is None


def test_colour_test_calls_a_skin_coloured_miss_skin_like():
    rgb = np.full((80, 80, 3), (200, 160, 140), np.uint8)  # skin everywhere
    gt = np.zeros((80, 80), bool)
    gt[20:60, 20:60] = True
    pred = np.zeros_like(gt)
    pred[30:50, 30:50] = True
    rgb[pred] = (150, 30, 40)  # wound bed only where the model hit

    result = colour_test(rgb, gt, pred)
    assert result is not None and result["skin_like"] is True

    rgb[gt] = (150, 30, 40)  # the whole label is wound-coloured
    assert colour_test(rgb, gt, pred)["skin_like"] is False


def test_colour_test_skips_regions_below_the_minimum():
    rgb = np.zeros((80, 80, 3), np.uint8)
    gt = np.zeros((80, 80), bool)
    gt[20:60, 20:60] = True
    assert colour_test(rgb, gt, gt.copy()) is None  # nothing missed
