# P02-S04 — Baseline Training and Checkpointing

> **Status: DEFERRED → SPEC-02-02.** The mechanisms are implemented and tested
> under SPEC-02-01. The real GPU run is executed and accepted under
> `SPEC-02-02-baseline-completion.md`.

## Purpose
Train the baseline reproducibly and create the first trustworthy reference result.

## Requirements
- **REQ-P02-S04-001:** Store model/data/training settings in configuration: manifests, resolution, batch size, LR, optimizer, loss, epochs, seed, device, augmentation and checkpoint policy.
- **REQ-P02-S04-002:** Set and record random seeds where appropriate and document known nondeterminism.
- **REQ-P02-S04-003:** Select and explain the optimizer.
- **REQ-P02-S04-004:** Training uses only train; validation is for selection; test is untouched until final evaluation.
- **REQ-P02-S04-005:** Checkpoints preserve model state and sufficient configuration/epoch/validation information; optimizer state when needed.
- **REQ-P02-S04-006:** Define checkpoint-selection metric before training.
- **REQ-P02-S04-007:** Log per epoch training loss, validation loss, selected validation metrics and LR/timing when useful.
- **REQ-P02-S04-008:** Fail clearly on data errors, invalid targets, non-finite loss or checkpoint-write failures.
- **REQ-P02-S04-009:** Resume support is preferred when practical; otherwise document why omitted.
- **REQ-P02-S04-010:** Do not perform a large hyperparameter sweep. Any corrective adjustment must be recorded.

## Acceptance
Training completes, logs/checkpoints exist, validation-based selection is reproducible, configuration is recorded and split isolation is preserved.
