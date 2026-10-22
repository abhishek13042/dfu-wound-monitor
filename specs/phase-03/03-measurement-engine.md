# P03-S03 — Wound Measurement Engine

## Status

`COMPLETED` — `src/measurement/engine.py`. It computes pixel area, perimeter, Feret diameters, components and confidence, and converts them to physical units only when a validated `pixels_per_mm` calibration is supplied. Config: `configs/measurement/measurement_v1.json`. Tests: `tests/measurement/test_p03_s03_measurement.py` (analytic shapes). Real-data agreement against ground-truth masks is reported in `reports/final/phase_06_validation_report.md`.

## Objective

Derive reproducible geometric measurements from a wound mask while explicitly
separating pixel measurements from calibrated physical measurements.

## Scope

Pixel area, perimeter, bounding box, connected components, shape descriptors,
optional calibration, confidence/warning fields, and provenance.

## Non-Goals

Clinical wound grading, healing claims, or automatic treatment decisions.

## Requirements

- **REQ-P03-S03-001:** Known binary masks SHALL produce deterministic geometric
  values within documented tolerances.
- **REQ-P03-S03-002:** Every result SHALL state `PIXEL_BASED` or
  `PHYSICALLY_CALIBRATED`.
- **REQ-P03-S03-003:** Physical units SHALL be emitted only when valid scale
  metadata is supplied.
- **REQ-P03-S03-004:** Empty, disconnected, malformed, and low-confidence masks
  SHALL have explicit behavior.
- **REQ-P03-S03-005:** Results SHALL preserve input, model, calibration, and
  configuration provenance.

## Contract

`MeasurementRequest(mask, calibration?, provenance)` produces a structured
`MeasurementResult` containing values, units, calibration status, warnings, and
provenance.

## Tests and Acceptance

Synthetic geometry fixtures, calibration tests, empty-mask tests, malformed
mask tests, and serialization round-trip tests SHALL pass.
