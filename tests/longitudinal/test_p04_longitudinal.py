"""P04-S01..S03: records, comparison and technical trends on SYNTHETIC data."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from src.inference.pipeline import AnalysisPipeline
from src.longitudinal.comparison import AVAILABLE, UNAVAILABLE, CompatibilityPolicy, MeasurementPoint, compare
from src.longitudinal.records import (
    AnalysisRecord,
    CaseRecord,
    ExaminationRecord,
    ImageRecord,
    RecordValidationError,
    analysis_record_from_outcome,
    image_record_from_outcome,
)
from src.longitudinal.trends import TREND_LABEL, build_trend
from src.measurement.engine import Calibration, measure

T0 = datetime(2026, 1, 5, 9, 30, tzinfo=timezone.utc)
SHA = "a" * 64
POLICY = CompatibilityPolicy()


def _provenance():
    return {"input": {"sha256": SHA}, "model": {"model_version": "m1"}, "preprocessing": {}, "postprocessing": {}}


def _point(case, day, side, *, model="m1", calibration=None, exam_id=None, captured=True, status="COMPLETED",
           exam_case=None):
    exam = ExaminationRecord.create(
        examination_id=exam_id or f"exam-{case.case_id}-{day}",
        case_id=case.case_id if exam_case is None else exam_case,
        captured_at=T0 + timedelta(days=day) if captured else None,
        timestamp_source="USER_ENTERED" if captured else "UNKNOWN",
    )
    if status == "COMPLETED":
        mask = np.zeros((200, 200), dtype=np.uint8)
        if side:
            mask[50:50 + side, 50:50 + side] = 1
        measurement = measure(mask, calibration=calibration).to_dict()
        measurement.pop("provenance")
        record = AnalysisRecord.create(analysis_id=f"ana-{exam.examination_id}", image_id=f"img-{exam.examination_id}",
                                       examination_id=exam.examination_id, status="COMPLETED",
                                       quality={"status": "ACCEPTED"}, model_version=model,
                                       measurement=measurement, calibration=measurement["calibration"],
                                       provenance=_provenance())
    else:
        record = AnalysisRecord.create(analysis_id=f"ana-{exam.examination_id}", image_id=f"img-{exam.examination_id}",
                                       examination_id=exam.examination_id, status="QUALITY_REJECTED",
                                       quality={"status": "REJECTED", "reason_codes": ["BLURRY"]})
    return MeasurementPoint(case, exam, record)


@pytest.fixture
def case():
    return CaseRecord.create(case_id="syn-case-1", identity_status="VERIFIED", data_source="SYNTHETIC")


# ---------------------------------------------------------------- P04-S01 records

def test_case_examination_image_are_distinct_records(case):
    exam = ExaminationRecord.create(case_id=case.case_id, captured_at=T0, timestamp_source="EXIF")
    image = ImageRecord.create(examination_id=exam.examination_id, sha256=SHA, format="PNG", width=10, height=10)
    ids = {case.case_id, exam.examination_id, image.image_id}
    assert len(ids) == 3 and exam.examination_id.startswith("exam-") and image.image_id.startswith("img-")
    assert image.examination_id == exam.examination_id


def test_unknown_identifiers_stay_unknown_and_filenames_are_not_parsed():
    exam = ExaminationRecord.create()
    image = ImageRecord.create(sha256=SHA, format="JPEG", width=4, height=4,
                               original_filename="patient_0042_visit_3_2025-03-01.jpg")
    assert exam.case_id is None and exam.captured_at is None and exam.timestamp_source == "UNKNOWN"
    assert image.examination_id is None
    assert image.original_filename == "patient_0042_visit_3_2025-03-01.jpg"
    assert "0042" not in json.dumps({k: v for k, v in image.to_dict().items() if k != "original_filename"})


@pytest.mark.parametrize(
    "factory, kwargs, field",
    [
        (ExaminationRecord, {"captured_at": datetime(2026, 1, 1), "timestamp_source": "EXIF"}, "captured_at"),
        (ExaminationRecord, {"captured_at": T0}, "__root__"),
        (ExaminationRecord, {"timestamp_source": "EXIF"}, "__root__"),
        (ExaminationRecord, {"captured_at": datetime.now(timezone.utc) + timedelta(days=2),
                             "timestamp_source": "USER_ENTERED"}, "__root__"),
        (ExaminationRecord, {"case_id": "has space"}, "case_id"),
        (ExaminationRecord, {"unexpected": 1}, "unexpected"),
        (ImageRecord, {"sha256": "xyz", "format": "PNG", "width": 1, "height": 1}, "sha256"),
        (ImageRecord, {"sha256": SHA, "format": "PNG", "width": 0, "height": 1}, "width"),
        (CaseRecord, {"identity_status": "VERIFIED", "data_source": "FUSEG2021"}, "__root__"),
        (CaseRecord, {"identity_status": "MAYBE"}, "identity_status"),
        (AnalysisRecord, {"image_id": "i1", "status": "COMPLETED", "quality": {}}, "__root__"),
        (AnalysisRecord, {"image_id": "i1", "status": "QUALITY_REJECTED", "quality": {"status": "ACCEPTED"}}, "__root__"),
        (AnalysisRecord, {"image_id": "i1", "status": "FAILED", "quality": {}}, "__root__"),
    ],
)
def test_invalid_records_raise_structured_errors(factory, kwargs, field):
    with pytest.raises(RecordValidationError) as info:
        factory.create(**kwargs)
    payload = info.value.to_dict()
    assert payload["code"] == "RECORD_INVALID" and payload["record_type"] == factory.__name__
    assert any(error["field"] == field for error in payload["errors"]), payload


def test_completed_analysis_requires_full_provenance():
    with pytest.raises(RecordValidationError):
        AnalysisRecord.create(image_id="i1", status="COMPLETED", quality={"status": "ACCEPTED"}, model_version="m",
                              measurement={"measurement_basis": "PIXEL_BASED"}, provenance={"input": {}})


def test_records_round_trip_through_json(case):
    point = _point(case, 0, 20, calibration=Calibration(4.0, "REFERENCE_MARKER"))
    for record in (point.case, point.examination, point.analysis):
        clone = type(record).from_json(json.dumps(record.to_dict()))
        assert clone == record
    with pytest.raises(RecordValidationError):
        ExaminationRecord.from_json('{"captured_at": "2026-01-01T00:00:00", "timestamp_source": "EXIF"}')


def test_pipeline_outcome_maps_to_records_with_provenance(tiny_engine, make_image):
    outcome = AnalysisPipeline(tiny_engine).analyze(make_image(size=(256, 200)), request_id="req-9",
                                                    calibration=Calibration(3.0, "USER_ENTERED"))
    image = image_record_from_outcome(outcome, "exam-1", original_filename="x.png")
    record = analysis_record_from_outcome(outcome, image)
    assert record.status == "COMPLETED" and record.model_version == "tiny-test-model"
    for section in ("input", "model", "preprocessing", "postprocessing", "measurement"):
        assert section in record.provenance
    assert record.provenance["input"]["sha256"] == image.sha256 == outcome.decoded.sha256
    assert record.calibration["pixels_per_mm"] == 3.0 and record.measurement_basis == "PHYSICALLY_CALIBRATED"


# ---------------------------------------------------------------- P04-S02 comparison

def test_valid_pair_gives_deterministic_changes(case):
    a, b = _point(case, 0, 40), _point(case, 14, 30)
    result = compare(b, a, POLICY)  # argument order does not matter
    assert result.status == AVAILABLE and result.interval_days == 14
    assert result.earlier["examination_id"] == a.examination.examination_id
    assert result.earlier["model_version"] == result.later["model_version"] == "m1"
    area = result.metrics["area"]
    assert (area["earlier"], area["later"], area["absolute_change"], area["percent_change"]) == (1600, 900, -700, -43.75)
    assert area["unit"] == "px^2"
    assert {w["code"] for w in result.warnings} == {"PIXEL_SCALE_NOT_CONTROLLED"}
    assert "not a clinical assessment" in result.label
    assert compare(a, b, POLICY).to_dict() == result.to_dict()


def test_policy_is_mandatory(case):
    with pytest.raises(ValueError):
        compare(_point(case, 0, 10), _point(case, 1, 10))


def test_calibrated_pair_uses_mm_and_warns_on_scale_change(case):
    a = _point(case, 0, 40, calibration=Calibration(4.0, "REFERENCE_MARKER"))
    b = _point(case, 7, 40, calibration=Calibration(5.0, "USER_ENTERED"))
    result = compare(a, b, POLICY)
    assert result.status == AVAILABLE and result.basis == "PHYSICALLY_CALIBRATED"
    assert result.metrics["area"]["earlier"] == 100.0 and result.metrics["area"]["later"] == 64.0
    assert result.metrics["area"]["unit"] == "mm^2"
    assert {"CALIBRATION_CHANGED", "CALIBRATION_METHOD_CHANGED"} <= {w["code"] for w in result.warnings}


@pytest.mark.parametrize(
    "build, reason",
    [
        (lambda c: (_point(c, 0, 20), _point(c, 3, 20, model="m2")), "MODEL_VERSION_MISMATCH"),
        (lambda c: (_point(c, 0, 20), _point(c, 3, 20, calibration=Calibration(4, "USER_ENTERED"))),
         "MEASUREMENT_BASIS_MISMATCH"),
        (lambda c: (_point(c, 0, 20), _point(c, 3, 20, captured=False)), "TIMESTAMP_MISSING"),
        (lambda c: (_point(c, 0, 20), _point(c, 0, 20, exam_id="other")), "SAME_TIMESTAMP"),
        (lambda c: (_point(c, 0, 20), _point(c, 3, 0, status="REJECTED")), "MEASUREMENT_MISSING"),
        (lambda c: (_point(c, 0, 20), _point(c, 3, 20, exam_case="someone-else")), "CASE_MISMATCH"),
    ],
)
def test_incompatible_pairs_are_unavailable(case, build, reason):
    result = compare(*build(case), POLICY)
    assert result.status == UNAVAILABLE and reason in result.reason_codes and result.metrics == {}
    assert result.earlier["analysis_id"] and result.later["analysis_id"]


def test_unknown_identity_and_cross_dataset_are_never_linked():
    public = [CaseRecord.create(case_id=f"fuseg-{i}", data_source="FUSEG2021", identity_status="UNVERIFIED")
              for i in range(2)]
    result = compare(_point(public[0], 0, 20), _point(public[1], 5, 20), POLICY)
    assert result.status == UNAVAILABLE
    assert {"IDENTITY_UNVERIFIED", "DIFFERENT_CASE"} <= set(result.reason_codes)
    relaxed = CompatibilityPolicy(require_verified_identity=False)
    assert "DIFFERENT_CASE" in compare(_point(public[0], 0, 20), _point(public[1], 5, 20), relaxed).reason_codes


def test_unknown_case_on_examination_is_unavailable(case):
    point = _point(case, 0, 20)
    orphan = MeasurementPoint(case, ExaminationRecord.create(examination_id="orphan", captured_at=T0 + timedelta(days=2),
                                                             timestamp_source="EXIF"), point.analysis)
    assert "CASE_UNKNOWN" in compare(point, orphan, POLICY).reason_codes


def test_zero_baseline_has_no_percentage(case):
    result = compare(_point(case, 0, 0), _point(case, 10, 20), POLICY)
    assert result.status == AVAILABLE
    assert result.metrics["area"]["state"] == "BASELINE_ZERO" and result.metrics["area"]["percent_change"] is None
    assert "BASELINE_ZERO" in {w["code"] for w in result.warnings}


# ---------------------------------------------------------------- P04-S03 trends

def _series(case):
    return [_point(case, day, side) for day, side in ((0, 40), (7, 36), (14, 30), (21, 24))]


def test_known_series_gives_expected_trend(case):
    trend = build_trend(list(reversed(_series(case))), POLICY)
    assert trend.status == AVAILABLE and trend.basis == "PIXEL_BASED" and trend.label == TREND_LABEL
    assert [row["values"]["area"] for row in trend.rows] == [1600, 1296, 900, 576]
    assert [row["days_since_baseline"] for row in trend.rows] == [0, 7, 14, 21]
    assert trend.rows[0]["is_baseline"] and trend.rows[0]["from_previous"] is None
    assert trend.rows[-1]["from_baseline"]["area"]["percent_change"] == -64.0
    assert trend.rows[2]["from_previous"]["area"]["absolute_change"] == -396
    assert "technical trend" in trend.to_markdown() and "Not a clinical assessment" in trend.to_csv()


def test_trend_is_reproducible(case, tmp_path):
    first, second = build_trend(_series(case), POLICY), build_trend(list(reversed(_series(case))), POLICY)
    assert first.to_dict() == second.to_dict() and first.trend_id == second.trend_id
    assert first.to_csv() == second.to_csv()
    a, b = first.plot(tmp_path / "a.png"), second.plot(tmp_path / "b.png")
    assert a.read_bytes() == b.read_bytes()
    changed = build_trend(_series(case)[:3], POLICY)
    assert changed.trend_id != first.trend_id


def test_missing_and_incompatible_points_are_excluded_with_reasons(case):
    points = _series(case) + [_point(case, 28, 0, status="REJECTED"), _point(case, 35, 20, model="m2"),
                              _point(case, 40, 20, captured=False, exam_id="no-time")]
    trend = build_trend(points, POLICY)
    assert trend.status == AVAILABLE and len(trend.rows) == 4
    reasons = {item["examination_id"]: item["reason_codes"] for item in trend.excluded}
    assert reasons[f"exam-{case.case_id}-28"] == ["MEASUREMENT_MISSING"]
    assert reasons[f"exam-{case.case_id}-35"] == ["MODEL_VERSION_MISMATCH"]
    assert "TIMESTAMP_MISSING" in reasons["no-time"]
    assert "EXAMINATIONS_EXCLUDED" in {w["code"] for w in trend.warnings}


def test_long_gap_is_flagged(case):
    trend = build_trend([_point(case, 0, 20), _point(case, 100, 18)], POLICY)
    assert "LONG_GAP" in trend.rows[1]["flags"]


@pytest.mark.parametrize("days", [[], [0]])
def test_no_baseline_or_single_point_is_unavailable(case, days):
    trend = build_trend([_point(case, d, 20) for d in days], POLICY)
    assert trend.status == UNAVAILABLE and "INSUFFICIENT_POINTS" in trend.reason_codes and trend.rows == []
    if not days:
        assert "NO_BASELINE" in trend.reason_codes


def test_zero_baseline_trend(case):
    trend = build_trend([_point(case, 0, 0), _point(case, 5, 10)], POLICY)
    assert trend.rows[1]["from_baseline"]["area"]["percent_change"] is None
    assert "BASELINE_ZERO" in trend.rows[1]["flags"]
    assert "n/a" in trend.to_markdown()


def test_mixed_cases_are_refused(case):
    other = CaseRecord.create(case_id="syn-case-2", identity_status="VERIFIED", data_source="SYNTHETIC")
    trend = build_trend([_point(case, 0, 20), _point(other, 3, 20)], POLICY)
    assert trend.status == UNAVAILABLE and trend.reason_codes == ["MIXED_CASES"]
