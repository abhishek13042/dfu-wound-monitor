# P06-S01 — End-to-End Validation and Error Analysis

## Status

`COMPLETED` — `scripts/evaluation/run_phase_06_validation.py` runs the deployed pipeline on FUSeg2021 test (191) and on the LowerLimb external set. Outputs: `reports/final/p06_validation_*.json` and `reports/final/phase_06_validation_report.md`, which presents the per-component metrics and distributions, and keeps the failure taxonomy separate from hypotheses.

## Objective

Validate the complete technical workflow and report observed failures without
fabricating clinical conclusions.

## Scope

Segmentation, quality, measurements, longitudinal comparison, API behavior,
integration tests, qualitative review, and structured error taxonomy.

## Non-Goals

Clinical validation, unsupported performance claims, or new model development.

## Requirements

- **REQ-P06-S01-001:** Each core component SHALL have task-appropriate metrics.
- **REQ-P06-S01-002:** Evaluation SHALL preserve split, dataset, and artifact
  provenance.
- **REQ-P06-S01-003:** Error analysis SHALL separate observed errors from
  hypotheses and cover representative failure types.
- **REQ-P06-S01-004:** Reports SHALL include distributions/counts, not only a
  single aggregate score.

## Tests and Acceptance

Independent metric checks, end-to-end fixtures, qualitative evidence review,
and report audit SHALL pass.
