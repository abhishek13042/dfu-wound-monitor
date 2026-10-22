# P02-S06 — Qualitative Evaluation and Error Review

> **Status: DEFERRED → SPEC-02-02.** The figure generator is implemented. The
> review needs predictions from the real run.

## Purpose
Understand baseline behavior rather than treating a single aggregate score as the whole result.

## Requirements
- **REQ-P02-S06-001:** Generate deterministic/documented representative good, mediocre and poor predictions.
- **REQ-P02-S06-002:** Show original image, ground truth, prediction and overlay/difference where applicable.
- **REQ-P02-S06-003:** Review observed failures such as missed wound, false positive, under/over-segmentation, poor boundary, small wound, low contrast, shadow, dressing/occlusion and unusual viewpoint. Only report categories actually observed.
- **REQ-P02-S06-004:** For representative failures record what happened, likely technical reason and evidence vs hypothesis.
- **REQ-P02-S06-005:** Do not convert model errors into unsupported clinical claims.
- **REQ-P02-S06-006:** Document baseline limitations.
- **REQ-P02-S06-007:** Suggest a small number of technically justified improvements for later phases without implementing the full advanced system.

## Acceptance
Predictions are visually inspected, representative successes/failures are documented, failure categories are evidence-based and improvement hypotheses are recorded.
