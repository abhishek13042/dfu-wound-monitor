# P05-S01 — Inference API Contract

## Status

`COMPLETED` — `src/api/app.py` and `src/api/schemas.py` (FastAPI `/api/v1`). Every error uses one envelope with category, code and failure_class. Health is split into `/health/live` and `/health/ready`. Upload limits are enforced, and quality rejections (422) are distinguished from model failures (500/503). Tests: `tests/api/test_p05_api.py`. Verified manually with the real checkpoint (see `reports/final/phase_06_validation_report.md`).

## Objective

Expose the validated inference workflow through a stable Python/API boundary.

## Scope

Request/response schemas, upload or image-reference handling, quality status,
inference status/results, structured errors, model version, and health checks.

## Non-Goals

Direct UI-to-model calls, authentication beyond the approved prototype scope,
or cloud scaling.

## Requirements

- **REQ-P05-S01-001:** API responses SHALL use versioned typed schemas.
- **REQ-P05-S01-002:** Invalid input, quality rejection, model failure, and
  infrastructure failure SHALL be distinguishable.
- **REQ-P05-S01-003:** Results SHALL include model/config/provenance references.
- **REQ-P05-S01-004:** API behavior SHALL be testable without a live external
  service.

## Tests and Acceptance

Contract, validation, error, health, deterministic fixture, and integration
tests SHALL pass with documented startup and request examples.
