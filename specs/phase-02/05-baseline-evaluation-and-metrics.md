# P02-S05 — Baseline Evaluation and Metrics

> **Status: DEFERRED → SPEC-02-02.** REQ-001 ("test evaluator") cannot be
> satisfied with the current split, for two reasons:
>
> - The FUSeg2021 public test masks are unreleased.
> - The official validation split is used for model selection.
>
> See *Evaluation split* in `SPEC-02-02-baseline-completion.md`.

## Purpose
Measure actual baseline performance as a trustworthy reference point for later improvements.

## Requirements
- **REQ-P02-S05-001:** Final evaluation uses the designated test split.
- **REQ-P02-S05-002:** Evaluate the checkpoint selected using the predefined validation rule.
- **REQ-P02-S05-003:** For segmentation, report appropriate Dice, IoU, precision and recall/sensitivity where applicable. For detection, report appropriate precision, recall, mAP@50 and mAP@50:95 where supported, plus FP/FN analysis.
- **REQ-P02-S05-004:** Define mathematically every reported metric and explain what high/low values and edge cases mean.
- **REQ-P02-S05-005:** Retain per-sample results where practical for later investigation.
- **REQ-P02-S05-006:** Define aggregate averaging method; do not mix incompatible aggregation methods without explanation.
- **REQ-P02-S05-007:** Explain why accuracy alone is insufficient when foreground/background or class imbalance is substantial.
- **REQ-P02-S05-008:** Every number must come from an actual run.
- **REQ-P02-S05-009:** Evaluation must be reproducible from the recorded checkpoint/configuration.
- **REQ-P02-S05-010:** Quantitative evaluation must be accompanied by P02-S06 qualitative inspection.

## Acceptance
Correct checkpoint is evaluated; actual predictions and task-appropriate metrics are saved; definitions and aggregation are documented; no test information influenced model selection.
