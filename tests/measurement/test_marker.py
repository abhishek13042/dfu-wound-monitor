"""P09-S01: reference-marker calibration on synthetic scenes with a known scale."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from PIL import Image

from src.inference.pipeline import COMPLETED, AnalysisPipeline
from src.measurement.calibration import resolve_calibration
from src.measurement.engine import LIMITATION, Calibration, MeasurementError
from src.measurement.marker import (
    AMBIGUOUS,
    ARUCO_MARKER,
    FOUND,
    NOT_FOUND,
    PARTIAL,
    TILTED,
    TOO_SMALL,
    WRONG_ID,
    MarkerConfig,
    MarkerReading,
    detect_marker,
)
from src.measurement.marker_synthetic import render_scene

CONFIG = MarkerConfig.load()


def _bar_mm(scene, calibration: Calibration) -> float:
    (x1, y1), (x2, y2) = scene.bar_px
    return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 / calibration.pixels_per_mm


# ------------------------------------------------------------ REQ-001 scale
@pytest.mark.parametrize("px_per_mm", [2.0, 3.5, 5.0])
def test_a_facing_marker_gives_the_true_scale(px_per_mm):
    scene = render_scene(px_per_mm=px_per_mm)
    reading = detect_marker(scene.image, CONFIG)
    assert reading.status == FOUND
    calibration = reading.calibration
    assert calibration.method == ARUCO_MARKER
    assert calibration.source == "aruco DICT_4X4_50 id 7"
    assert calibration.pixels_per_mm == pytest.approx(px_per_mm, rel=0.01)
    assert 0 < calibration.uncertainty_pct < 5
    assert _bar_mm(scene, calibration) == pytest.approx(60.0, rel=0.01)
    assert reading.to_dict()["config"]["version"] == "p09-s01-v1"


def test_a_slight_tilt_and_noise_still_measure_within_five_percent():
    scene = render_scene(px_per_mm=5.0, tilt_deg=10, noise=6, seed=3)
    reading = detect_marker(scene.image, CONFIG)
    assert reading.status == FOUND
    assert _bar_mm(scene, reading.calibration) == pytest.approx(60.0, rel=0.05)


# --------------------------------------------------------- REQ-002 fallbacks
@pytest.mark.parametrize(("kwargs", "status"), [
    ({"with_marker": False}, NOT_FOUND),
    ({"marker_id": 3}, WRONG_ID),
    ({"px_per_mm": 1.0}, TOO_SMALL),
    ({"tilt_deg": 40}, TILTED),
    ({"offset_px": (-17, 0)}, PARTIAL),
])
def test_an_unusable_marker_gives_a_reason_and_no_scale(kwargs, status):
    scene = render_scene(**{"px_per_mm": 5.0, **kwargs})
    reading = detect_marker(scene.image, CONFIG)
    assert reading.status == status
    assert reading.calibration is None


def test_two_copies_of_the_marker_are_ambiguous():
    scene = render_scene(px_per_mm=3.0)
    corners = detect_marker(scene.image, CONFIG).details["corners_px"]
    left, top = (int(min(c[i] for c in corners)) - 8 for i in (0, 1))
    size = int(max(c[0] for c in corners)) + 8 - left
    image = scene.image.copy()
    image[top:top + size, 470:470 + size] = scene.image[top:top + size, left:left + size]
    reading = detect_marker(image, CONFIG)
    assert reading.status == AMBIGUOUS and reading.calibration is None


def test_a_rejected_marker_never_supplies_a_scale():
    rejected = MarkerReading(TILTED)
    assert resolve_calibration(None, rejected, 5.0) == (None, [
        {"code": TILTED, "message": "The marker is seen at too steep an angle for a reliable scale; "
                                    "only pixel measurements are reported"}])
    user = Calibration(4.0, "USER_ENTERED")
    calibration, warnings = resolve_calibration(user, rejected, 5.0)
    assert calibration is user and warnings[0]["message"].endswith("the scale you entered is used")


def test_no_marker_leaves_the_users_scale_without_a_warning():
    user = Calibration(4.0, "USER_ENTERED")
    assert resolve_calibration(user, MarkerReading(NOT_FOUND), 5.0) == (user, [])
    assert resolve_calibration(None, None, 5.0) == (None, [])


# ---------------------------------------------------------- REQ-004 conflict
def test_the_marker_wins_and_a_disagreeing_user_scale_is_flagged():
    marker = MarkerReading(FOUND, Calibration(5.0, ARUCO_MARKER, "aruco DICT_4X4_50 id 7", 1.0))
    close = resolve_calibration(Calibration(5.2, "USER_ENTERED"), marker, 5.0)
    assert close == (marker.calibration, [])
    calibration, warnings = resolve_calibration(Calibration(6.0, "USER_ENTERED"), marker, 5.0)
    assert calibration is marker.calibration
    assert warnings[0]["code"] == "SCALE_CONFLICT" and "20.0% apart" in warnings[0]["message"]


# ------------------------------------------------------- pipeline end to end
def _png(array) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(array).save(buffer, format="PNG")
    return buffer.getvalue()


def test_the_pipeline_measures_with_the_marker_and_records_why(tiny_engine):
    scene = render_scene(px_per_mm=4.0, textured_background=True, noise=4, seed=1)
    outcome = AnalysisPipeline(tiny_engine).analyze(_png(scene.image), calibration=Calibration(6.0, "USER_ENTERED"))
    assert outcome.status == COMPLETED, outcome.quality
    measurement = outcome.measurement
    assert measurement.calibration["method"] == ARUCO_MARKER
    assert measurement.calibration["pixels_per_mm"] == pytest.approx(4.0, rel=0.02)
    assert measurement.provenance["marker"]["status"] == FOUND
    assert "SCALE_CONFLICT" in {w["code"] for w in outcome.warnings}
    assert "UNCALIBRATED" not in {w["code"] for w in outcome.warnings}


def test_the_pipeline_falls_back_to_pixels_with_the_reason(tiny_engine):
    scene = render_scene(px_per_mm=5.0, tilt_deg=40, textured_background=True, noise=4, seed=2)
    outcome = AnalysisPipeline(tiny_engine).analyze(_png(scene.image))
    assert outcome.status == COMPLETED, outcome.quality
    assert outcome.measurement.calibration is None
    codes = [w["code"] for w in outcome.warnings]
    assert TILTED in codes and "UNCALIBRATED" in codes


def test_a_disabled_marker_config_skips_detection(tiny_engine, tmp_path):
    raw = json.loads(open(CONFIG.path, encoding="utf-8").read())
    path = tmp_path / "marker.json"
    path.write_text(json.dumps({**raw, "enabled": False}), encoding="utf-8")
    scene = render_scene(px_per_mm=4.0, textured_background=True, noise=4, seed=1)
    outcome = AnalysisPipeline(tiny_engine, marker_config=MarkerConfig.load(path)).analyze(_png(scene.image))
    assert outcome.measurement.calibration is None and "marker" not in outcome.measurement.provenance


def test_a_bad_marker_config_is_refused(tmp_path):
    raw = json.loads(open(CONFIG.path, encoding="utf-8").read())
    for change in ({"dictionary": "DICT_NOPE"}, {"side_mm": 0}):
        path = tmp_path / "marker.json"
        path.write_text(json.dumps({**raw, **change}), encoding="utf-8")
        with pytest.raises(MeasurementError):
            MarkerConfig.load(path)


# ------------------------------------------------------- REQ-005 limitation
def test_results_say_a_single_photo_gives_an_estimate():
    assert "single photo are estimates" in LIMITATION


# ---------------------------------------------------------- REQ-003 tooling
def test_the_validation_script_reads_a_manifest_of_photos(tmp_path):
    from scripts.evaluation.run_marker_validation import main

    images = []
    for index, tilt in enumerate((0, 40)):
        scene = render_scene(px_per_mm=4.0, tilt_deg=tilt, textured_background=True, seed=index)
        Image.fromarray(scene.image).save(tmp_path / f"photo{index}.png")
        images.append({"path": f"photo{index}.png", "distance_cm": 40, "angle_deg": tilt,
                       "object": {"p1": list(scene.bar_px[0]), "p2": list(scene.bar_px[1]), "true_mm": 60.0}})
    (tmp_path / "manifest.json").write_text(json.dumps({"images": images}), encoding="utf-8")
    out = tmp_path / "report.json"
    assert main(["--data", str(tmp_path / "manifest.json"), "--out", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["mode"] == "REAL_PHOTOS" and report["overall"]["accepted"] == 1
    assert [row["status"] for row in report["rows"]] == [FOUND, TILTED]
    assert abs(report["rows"][0]["error_pct"]) < 1.0


def test_the_marking_tool_reads_names_and_writes_a_manifest_the_validation_script_accepts(tmp_path):
    from scripts.evaluation.run_marker_validation import main as validate
    from scripts.measurement.mark_object_ends import (
        entry_for,
        load_manifest,
        parse_name,
        pending_photos,
        save_manifest,
    )

    assert parse_name(Path("d30_a15_ruler-100mm_01.jpg")) == {
        "distance_cm": 30.0, "angle_deg": 15.0, "object_name": "ruler", "true_mm": 100.0}
    with pytest.raises(ValueError):
        parse_name(Path("IMG_0001.jpg"))

    scene = render_scene(px_per_mm=4.0, tilt_deg=0, textured_background=True, seed=0)
    photo = tmp_path / "d40_a0_bar-60mm_01.png"
    Image.fromarray(scene.image).save(photo)
    manifest_path = tmp_path / "manifest.json"
    manifest = load_manifest(manifest_path)
    assert pending_photos(tmp_path, manifest) == [photo]
    manifest["images"].append(entry_for(photo, tmp_path, list(scene.bar_px[0]), list(scene.bar_px[1])))
    save_manifest(manifest_path, manifest)
    assert pending_photos(tmp_path, load_manifest(manifest_path)) == []

    out = tmp_path / "report.json"
    assert validate(["--data", str(manifest_path), "--out", str(out)]) == 0
    row = json.loads(out.read_text(encoding="utf-8"))["rows"][0]
    assert row["distance_cm"] == 40 and row["angle_deg"] == 0 and abs(row["error_pct"]) < 1.0
