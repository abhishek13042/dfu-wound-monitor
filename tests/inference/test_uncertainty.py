"""P09-S02: the flip-TTA disagreement summary."""

from __future__ import annotations

import json

import numpy as np
import pytest

from src.inference.engine import InferenceRequest
from src.inference.errors import ConfigError
from src.inference.uncertainty import MASK_AND_BAND, METHOD, WHOLE_IMAGE, UncertaintyConfig, tta_disagreement

ROOT_REPORT = "reports/final/p09_s02_uncertainty.json"


# ------------------------------------------------------- REQ-002 known maths
def test_disagreement_on_known_inputs():
    mask = np.zeros((4, 4), bool)
    mask[1:3, 1:3] = True
    views = np.zeros((2, 4, 4), np.float32)
    views[1, mask] = 0.5          # the two views differ by 0.5 inside the mask only
    summary = tta_disagreement(views, mask, band_px=0)
    assert summary["tta_disagreement"] == pytest.approx(0.5)
    assert summary["method"] == METHOD and summary["region"] == MASK_AND_BAND and summary["region_pixels"] == 4
    widened = tta_disagreement(views, mask, band_px=1)
    assert widened["region_pixels"] > 4 and widened["tta_disagreement"] < 0.5


def test_disagreement_averages_every_pair_of_views():
    views = np.stack([np.full((3, 3), v, np.float32) for v in (0.0, 0.2, 0.6)])
    # pairs: 0.2, 0.6, 0.4 -> mean 0.4
    assert tta_disagreement(views, np.ones((3, 3), bool), 0)["tta_disagreement"] == pytest.approx(0.4)


def test_identical_views_disagree_by_nothing():
    views = np.repeat(np.random.default_rng(0).random((1, 8, 8), dtype=np.float32), 4, axis=0)
    assert tta_disagreement(views, np.ones((8, 8), bool), 2)["tta_disagreement"] == 0.0


def test_an_empty_mask_is_summarised_over_the_whole_image_and_flagged():
    views = np.stack([np.zeros((5, 5), np.float32), np.full((5, 5), 0.1, np.float32)])
    summary = tta_disagreement(views, np.zeros((5, 5), bool), 3)
    assert summary["region"] == WHOLE_IMAGE and summary["empty_mask"] is True and summary["region_pixels"] == 25


def test_one_view_has_nothing_to_compare():
    assert tta_disagreement(np.zeros((1, 4, 4), np.float32), np.ones((4, 4), bool), 1) is None


def test_mismatched_shapes_are_refused():
    with pytest.raises(ValueError):
        tta_disagreement(np.zeros((2, 4, 4), np.float32), np.ones((3, 3), bool), 1)


def test_a_bad_config_is_refused(tmp_path):
    for raw in ({"version": "x", "method": "other", "band_px": 1, "summary_shown": False},
                {"version": "x", "method": METHOD, "band_px": -1, "summary_shown": False}, {"method": METHOD}):
        path = tmp_path / "u.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with pytest.raises(ConfigError):
            UncertaintyConfig.load(path)


# ------------------------------------------------------- engine end to end
def test_the_engine_stores_the_summary_without_changing_the_mask(tiny_engine, tmp_path):
    from tests.conftest import textured_png

    path = textured_png(tmp_path / "a.png")
    result = tiny_engine.predict(InferenceRequest(path))
    summary = result.summary()["uncertainty"]
    assert summary["method"] == METHOD and summary["views"] == 4
    assert 0.0 <= summary["tta_disagreement"] <= 1.0
    assert summary["config_version"] == "p09-s02-v1"
    assert summary["summary_shown"] is tiny_engine.uncertainty_config.summary_shown

    # The mean of the views is still the probability map the mask is cut from (bit for bit, as before).
    from src.segmentation.dataset import preprocess_image
    from src.segmentation.inference import predict_logits_tta

    cfg = tiny_engine.config
    decoded = tiny_engine.decode(path)
    tensor = preprocess_image(decoded.image, cfg.input_height, cfg.input_width,
                              list(cfg.normalize_mean), list(cfg.normalize_std)).unsqueeze(0)
    assert np.array_equal(tiny_engine._probabilities(tensor).detach().numpy(),
                          predict_logits_tta(tiny_engine.model, tensor, tta=True).detach().numpy())


def test_without_tta_there_is_no_summary(tiny_engine, tmp_path):
    from dataclasses import replace

    from tests.conftest import textured_png

    engine = tiny_engine
    original = engine.config
    try:
        engine.config = replace(original, tta=False)
        assert engine.predict(InferenceRequest(textured_png(tmp_path / "b.png"))).uncertainty is None
    finally:
        engine.config = original


# ------------------------------------------------------ REQ-003 study gate
def test_the_shown_flag_follows_the_study_decision():
    from pathlib import Path

    config = UncertaintyConfig.load()
    report = Path(__file__).resolve().parents[2] / ROOT_REPORT
    if not report.exists():
        assert config.summary_shown is False, "the summary may not be shown before the study has run"
        return
    decision = json.loads(report.read_text(encoding="utf-8"))["decision"]
    assert config.summary_shown is decision["show_summary"]
