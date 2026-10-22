# P04-S01 — Examination and Case Data Contract

## Status

`COMPLETED` — `src/longitudinal/records.py` provides versioned pydantic records for case, examination, analysis and calibration, with validation errors (`RecordValidationError`). Tests: `tests/longitudinal/test_p04_longitudinal.py`.

## Objective

Define the records needed to represent cases, examinations, images, inference
results, segmentations, measurements, and provenance.

## Scope

Typed schemas for case references, examination timestamps, image references,
quality results, model outputs, measurements, and technical failures.

## Non-Goals

Inferring patient identity, clinical diagnosis, or database implementation.

## Requirements

- **REQ-P04-S01-001:** An examination SHALL be distinct from a case and image.
- **REQ-P04-S01-002:** Unknown patient/examination identifiers SHALL remain
  unknown and SHALL NOT be inferred from filenames.
- **REQ-P04-S01-003:** Results SHALL preserve model, input, preprocessing, and
  calibration provenance.
- **REQ-P04-S01-004:** Invalid records SHALL fail with structured validation
  errors.

## Tests and Acceptance

Schema validation, unknown-identifier, timestamp, provenance, invalid-record,
and serialization tests SHALL pass.
