"""P03-S02: image quality gate (REQ-P03-S02-001..004)."""

from __future__ import annotations

import io
import json

import numpy as np
import pytest
from PIL import Image
from scipy import ndimage

from src.inference.errors import ConfigError
from src.quality.gate import ACCEPTED, REASON_CODES, REJECTED, QualityConfig, QualityGate
from tests.conftest import textured_png


@pytest.fixture(scope="module")
def gate():
    return QualityGate()


def _png(array: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(np.clip(array, 0, 255).astype(np.uint8)).save(buffer, format="PNG")
    return buffer.getvalue()


def _textured(width=256, height=200, seed=3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = np.full((height, width, 3), (170, 120, 100), dtype=np.float32)
    yy, xx = np.mgrid[:height, :width]
    base[((yy - height / 2) ** 2 + (xx - width / 2) ** 2) < (min(height, width) / 4) ** 2] = (150, 40, 40)
    return base + rng.normal(0, 30, base.shape)


def test_valid_image_is_accepted_with_full_record(gate):
    result = gate.evaluate(_png(_textured()))
    assert result.status == ACCEPTED and result.accepted and result.reason_codes == []
    assert set(result.thresholds) == set(gate.config.checks)
    for key in ("laplacian_variance", "mean_luminance", "glare_fraction", "content_fraction", "entropy"):
        assert key in result.measurements
    assert result.config_reference["version"] == "p03-s02-v1" and len(result.config_reference["sha256"]) == 64
    json.dumps(result.to_dict())  # serialisable


def test_textured_fixture_from_conftest_passes_when_large_enough(gate, tmp_path):
    assert gate.evaluate(textured_png(tmp_path / "ok.png", size=(256, 200))).accepted


@pytest.mark.parametrize(
    "name, make, expected",
    [
        ("tiny", lambda: _textured(100, 90), "TOO_SMALL"),
        ("aspect", lambda: _textured(1000, 200), "BAD_ASPECT_RATIO"),
        ("blank", lambda: np.full((256, 256, 3), 128.0), "INSUFFICIENT_CONTENT"),
        ("letterboxed", lambda: np.pad(_textured(60, 256), ((0, 0), (98, 98), (0, 0))), "INSUFFICIENT_CONTENT"),
        ("blurred", lambda: ndimage.gaussian_filter(_textured(), sigma=(6, 6, 0)), "BLURRY"),
        ("dark", lambda: _textured() * 0.12, "UNDEREXPOSED"),
        ("bright", lambda: np.full((256, 256, 3), 246.0) + np.random.default_rng(0).normal(0, 4, (256, 256, 3)),
         "OVEREXPOSED"),
        ("flat", lambda: np.full((256, 256, 3), 128.0) + np.random.default_rng(0).normal(0, 3, (256, 256, 3)),
         "LOW_CONTRAST"),
    ],
)
def test_each_reason_code_is_produced(gate, name, make, expected):
    result = gate.evaluate(_png(make()))
    assert result.status == REJECTED, (name, result.measurements)
    assert expected in result.reason_codes, (name, result.reason_codes, result.measurements)
    assert set(result.reason_codes) <= set(REASON_CODES)


def test_glare_patch_is_rejected_for_glare(gate):
    image = _textured()
    image[:, :120] = 252  # ~47% specular white, below the overexposure limit
    result = gate.evaluate(_png(image))
    assert result.reason_codes == ["GLARE"], result.measurements


def test_multiple_reasons_are_all_reported(gate):
    result = gate.evaluate(_png(ndimage.gaussian_filter(_textured(100, 90), sigma=(6, 6, 0)) * 0.12))
    assert {"TOO_SMALL", "BLURRY", "UNDEREXPOSED"} <= set(result.reason_codes)


@pytest.mark.parametrize("payload", [b"", b"not an image at all", _png(_textured())[:200]])
def test_unreadable_input_is_rejected_not_raised(gate, payload):
    result = gate.evaluate(payload)
    assert result.status == REJECTED and result.reason_codes == ["UNREADABLE"]
    assert result.details["input_error"]["category"] == "INPUT"


def test_disallowed_format_is_unreadable(gate):
    buffer = io.BytesIO()
    Image.fromarray(_textured().astype(np.uint8)).save(buffer, format="GIF")
    result = gate.evaluate(buffer.getvalue(), allowed_formats=["PNG", "JPEG"])
    assert result.reason_codes == ["UNREADABLE"]


def _passing_measures(checks):
    return {
        "width": checks["min_side_px"], "height": checks["min_side_px"] * checks["max_aspect_ratio"],
        "content_fraction": checks["min_content_fraction"], "entropy": checks["min_entropy_bits"],
        "laplacian_variance": checks["min_laplacian_variance"], "mean_luminance": checks["min_mean_luminance"],
        "dark_fraction": checks["max_dark_fraction"], "bright_fraction": checks["max_bright_fraction"],
        "luminance_std": checks["min_luminance_std"], "glare_fraction": checks["max_glare_fraction"],
    }


def test_values_exactly_at_threshold_are_accepted(gate):
    status, reasons, _ = gate._decide(_passing_measures(gate.config.checks))
    assert (status, reasons) == (ACCEPTED, [])
    upper = dict(_passing_measures(gate.config.checks), mean_luminance=gate.config.checks["max_mean_luminance"])
    assert gate._decide(upper)[0] == ACCEPTED


@pytest.mark.parametrize(
    "key, delta, reason",
    [
        ("width", -1, "TOO_SMALL"),
        ("content_fraction", -1e-6, "INSUFFICIENT_CONTENT"),
        ("entropy", -1e-6, "INSUFFICIENT_CONTENT"),
        ("laplacian_variance", -1e-6, "BLURRY"),
        ("mean_luminance", -1e-6, "UNDEREXPOSED"),
        ("dark_fraction", 1e-6, "UNDEREXPOSED"),
        ("bright_fraction", 1e-6, "OVEREXPOSED"),
        ("luminance_std", -1e-6, "LOW_CONTRAST"),
        ("glare_fraction", 1e-6, "GLARE"),
    ],
)
def test_values_just_beyond_threshold_are_rejected(gate, key, delta, reason):
    measures = _passing_measures(gate.config.checks)
    measures[key] += delta
    status, reasons, _ = gate._decide(measures)
    assert status == REJECTED and reason in reasons


def test_gate_is_deterministic(gate):
    payload = _png(_textured())
    assert gate.evaluate(payload).to_dict() == gate.evaluate(payload).to_dict()


def _write_config(tmp_path, mutate):
    from src.quality.gate import DEFAULT_QUALITY_CONFIG

    raw = json.loads(DEFAULT_QUALITY_CONFIG.read_text(encoding="utf-8"))
    mutate(raw)
    path = tmp_path / "quality.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "mutate",
    [
        lambda raw: raw["checks"].pop("min_laplacian_variance"),
        lambda raw: raw["checks"].__setitem__("max_glare_fraction", -0.1),
        lambda raw: raw["checks"].__setitem__("min_side_px", "128"),
        lambda raw: raw["checks"].__setitem__("min_mean_luminance", 250),
        lambda raw: raw.pop("quality_config_version"),
    ],
)
def test_invalid_configs_are_refused(tmp_path, mutate):
    with pytest.raises(ConfigError):
        QualityConfig.load(_write_config(tmp_path, mutate))


def test_missing_and_malformed_config_files(tmp_path):
    with pytest.raises(ConfigError):
        QualityConfig.load(tmp_path / "absent.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError):
        QualityConfig.load(bad)


def test_stricter_config_changes_the_decision(tmp_path):
    path = _write_config(tmp_path, lambda raw: raw["checks"].__setitem__("min_side_px", 400))
    result = QualityGate(QualityConfig.load(path)).evaluate(_png(_textured()))
    assert result.reason_codes == ["TOO_SMALL"] and result.thresholds["min_side_px"] == 400
