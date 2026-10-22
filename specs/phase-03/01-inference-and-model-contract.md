# P03-S01 — Inference and Model Artifact Contract

## Status

`COMPLETED` — `src/inference/engine.py` (config-pinned SPEC-02-03 checkpoint with SHA-256 verification, decode/format/size validation, deterministic CPU inference with flip TTA, threshold 0.40, min component 128 px) and `src/inference/pipeline.py` (decode → quality gate → segmentation → measurement). Contract: `configs/inference/spec_02_03_inference.json`. Tests: `tests/integration/test_p03_s01_inference.py`, `tests/integration/test_p03_pipeline.py`. End-to-end parity with Phase 02 held-out Dice: `reports/final/p06_validation_fuseg2021_test.json` (`phase_02_cross_check`).

## Objective

Turn the validated segmentation checkpoint into a deterministic, versioned
inference capability.

## Scope

Input decoding, shared preprocessing, checkpoint/config loading, inference,
thresholding, mask/probability output, provenance, and structured failures.

## Non-Goals

New model training, advanced segmentation, API endpoints, or clinical claims.

## Requirements

- **REQ-P03-S01-001:** Inference SHALL reuse the training preprocessing
  contract without silent overrides.
- **REQ-P03-S01-002:** Output SHALL include model version, config reference,
  input reference, probability mask, binary mask, and execution metadata.
- **REQ-P03-S01-003:** Missing, corrupt, incompatible, or malformed inputs and
  checkpoints SHALL produce typed errors.
- **REQ-P03-S01-004:** Repeated inference with the same inputs/config SHALL be
  deterministic within the declared runtime policy.

## Contract

`InferenceRequest(image, model_artifact, threshold, config)` produces
`InferenceResult(probability_mask, binary_mask, provenance, warnings)` or a
structured `InferenceError`.

## Tests and Acceptance

Controlled image fixtures, checkpoint compatibility tests, deterministic
repeatability tests, malformed-input tests, and provenance assertions SHALL
pass. The output schema and a reproducible command SHALL be documented.
