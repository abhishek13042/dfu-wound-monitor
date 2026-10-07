# P02-S07 — Experiment, Reproducibility and Baseline Report

## Purpose
Turn the baseline run into a durable artifact that future models can be compared against.

## Experiment record
Record: experiment_id, date, dataset/version, manifest version, model, pretrained weights, resolution, batch size, epochs, optimizer, LR, loss, augmentation, seed, device, checkpoint, validation metrics, test metrics and notes.

## Requirements
- **REQ-P02-S07-001:** Every run has a unique experiment ID.
- **REQ-P02-S07-002:** Configuration is complete enough to understand the run.
- **REQ-P02-S07-003:** Record exact dataset/manifest provenance.
- **REQ-P02-S07-004:** Record checkpoint provenance for reported test results.
- **REQ-P02-S07-005:** Every metric points to a concrete experiment/evaluation output.
- **REQ-P02-S07-006:** Document training, evaluation and inference/visualization commands where implemented.
- **REQ-P02-S07-007:** Baseline report contains problem, dataset, split, preprocessing, model, loss, training, metrics, quantitative results, qualitative examples, failures, limitations and next-step hypotheses.
- **REQ-P02-S07-008:** Do not claim state-of-the-art, clinical usefulness, production readiness or improvement without comparative evidence.
- **REQ-P02-S07-009:** Update existing `specs/TRACEABILITY.md`.
- **REQ-P02-S07-010:** Update existing `specs/MASTER_TRACKER.md`.
- **REQ-P02-S07-011:** Explicitly confirm no Phase 03+ work was started.

## Acceptance
Baseline is reproducible, documented, quantitatively and qualitatively evaluated, traceable, and all tests pass.
