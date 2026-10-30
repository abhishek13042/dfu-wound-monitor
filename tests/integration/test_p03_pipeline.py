"""P03 integration: decode -> quality gate -> inference -> measurement."""

from __future__ import annotations

import io
import json

import numpy as np
import pytest
from PIL import Image

from src.inference.errors import InputError
from src.inference.pipeline import COMPLETED, QUALITY_REJECTED, AnalysisPipeline
from src.measurement.engine import PHYSICALLY_CALIBRATED, PIXEL_BASED, Calibration


class SpyEngine:
    """Wraps the real engine and records whether the model was called."""

    def __init__(self, engine):
        self.engine, self.predict_calls = engine, 0
        self.config = engine.config

    def decode(self, source):
        return self.engine.decode(source)

    def predict(self, request):
        self.predict_calls += 1
        return self.engine.predict(request)


@pytest.fixture
def spy(tiny_engine):
    return SpyEngine(tiny_engine)


def test_accepted_image_runs_all_stages(spy, make_image):
    outcome = AnalysisPipeline(spy).analyze(make_image(size=(256, 200)), request_id="req-1")
    assert outcome.status == COMPLETED and spy.predict_calls == 1
    assert outcome.inference.binary_mask.shape == (200, 256)
    assert outcome.measurement.measurement_basis == PIXEL_BASED
    assert outcome.measurement.provenance["request_id"] == "req-1"
    assert outcome.measurement.provenance["input"]["sha256"] == outcome.decoded.sha256
    payload = json.loads(json.dumps(outcome.to_dict()))
    assert payload["quality"]["status"] == "ACCEPTED" and payload["measurement"] is not None


def test_rejected_image_never_reaches_the_model(spy):
    buffer = io.BytesIO()
    Image.fromarray(np.full((256, 256, 3), 128, dtype=np.uint8)).save(buffer, format="PNG")
    outcome = AnalysisPipeline(spy).analyze(buffer.getvalue())
    assert outcome.status == QUALITY_REJECTED and spy.predict_calls == 0
    assert outcome.inference is None and outcome.measurement is None
    assert "INSUFFICIENT_CONTENT" in outcome.quality.reason_codes
    assert outcome.to_dict()["measurement"] is None


def test_invalid_input_raises_typed_error_without_model_call(spy):
    with pytest.raises(InputError):
        AnalysisPipeline(spy).analyze(b"garbage")
    assert spy.predict_calls == 0


def test_calibration_flows_through(spy, make_image):
    outcome = AnalysisPipeline(spy).analyze(make_image(size=(256, 200)),
                                            calibration=Calibration(5.0, "USER_ENTERED"))
    assert outcome.measurement.measurement_basis == PHYSICALLY_CALIBRATED
    assert outcome.measurement.calibration["pixels_per_mm"] == 5.0


def test_pipeline_is_repeatable(spy, make_image):
    pipeline = AnalysisPipeline(spy)
    path = make_image(size=(256, 200))
    first, second = pipeline.analyze(path, request_id="r"), pipeline.analyze(path, request_id="r")
    assert np.array_equal(first.inference.binary_mask, second.inference.binary_mask)
    assert first.measurement.pixel == second.measurement.pixel
