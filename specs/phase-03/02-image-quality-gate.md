# P03-S02 — Image Quality Gate

## Status

`COMPLETED` — `src/quality/gate.py` and `src/quality/measures.py` (decodability, size, aspect ratio, under- and over-exposure, glare, low contrast, insufficient content and blur, each with a machine-readable reason code). Thresholds come from `configs/quality/` and were calibrated on the FUSeg2021 train distribution (`reports/quality/quality_gate_calibration.json`). The gate rejected 8 LowerLimb images as BLURRY, which is recorded as a domain-shift observation and was not tuned away. Tests: `tests/quality/test_p03_s02_quality_gate.py`.

## Objective

Reject technically unsuitable images before model inference with explicit,
configuration-driven reasons.

## Scope

Unreadable input, dimensions, blur, illumination, glare, field of view, and
quality result serialization.

## Non-Goals

Clinical diagnosis, wound severity classification, or learned quality models
without a separately approved specification.

## Requirements

- **REQ-P03-S02-001:** The gate SHALL return `ACCEPTED` or `REJECTED` with
  deterministic reason codes and measured values.
- **REQ-P03-S02-002:** Thresholds SHALL be configuration-driven and recorded in
  the result.
- **REQ-P03-S02-003:** Rejected inputs SHALL bypass downstream inference.
- **REQ-P03-S02-004:** Quality failure SHALL remain distinguishable from model
  and infrastructure failure.

## Contract

`QualityRequest(image, quality_config)` produces
`QualityResult(status, reason_codes, measurements, config_reference)`.

## Tests and Acceptance

Fixtures SHALL cover every rejection reason, borderline thresholds, valid
images, and unreadable files. Integration tests SHALL prove rejected images do
not invoke the model.
