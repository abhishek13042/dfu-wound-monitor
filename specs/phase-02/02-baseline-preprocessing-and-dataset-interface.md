# P02-S02 — Baseline Preprocessing and Dataset Interface

## Purpose
Build the reproducible bridge from Phase 01 manifests/annotations to the baseline model.

## Requirements
- **REQ-P02-S02-001:** Load from Phase 01 manifests; do not rediscover or reshuffle data independently.
- **REQ-P02-S02-002:** Maintain correct image/target alignment.
- **REQ-P02-S02-003:** Document every preprocessing step: decode, color conversion, resize, normalization and target conversion as applicable.
- **REQ-P02-S02-004:** Training augmentation, if used, is train-only and transforms images/targets consistently.
- **REQ-P02-S02-005:** Validation/test preprocessing is deterministic.
- **REQ-P02-S02-006:** Document image/target/batch/model tensor shapes.
- **REQ-P02-S02-007:** Test coordinate/mask correctness after spatial transforms.
- **REQ-P02-S02-008:** Phase 01 invalid samples cannot silently enter training.
- **REQ-P02-S02-009:** Preserve Phase 01 split assignments.
- **REQ-P02-S02-010:** Visually inspect loaded samples before full training.

## Tests
Image loading, missing paths, malformed targets, shape consistency, split isolation, deterministic evaluation preprocessing, annotation alignment.

## Acceptance
Batches can be produced directly from Phase 01 data, and visual inspection confirms correct targets after preprocessing.
