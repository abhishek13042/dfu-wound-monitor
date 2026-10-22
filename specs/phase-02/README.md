# Phase 02 — Baseline Model

## Purpose
Establish the first reproducible machine-learning baseline for DFU-WoundMonitor. The project master plan requires a baseline before advanced detection/segmentation. The exact baseline must be selected from Phase 01 evidence, not popularity.

## Order

P02-S01 Baseline Task & Model Selection → P02-S02 Preprocessing & Dataset
Interface → P02-S03 Baseline Model → SPEC-02-02 Baseline Run, Evaluation, and
Error Review. SPEC-02-02 absorbs the remaining execution responsibilities that
were previously split across P02-S04 through P02-S07.

## Source-grounded constraints
The master plan allows a simple segmentation model or standard pretrained detection model, says the exact model should be chosen after inspecting the dataset, and explicitly says not to choose YOLO merely because it is popular. Explain model selection. Never fabricate metrics.

## Phase boundary
Allowed: one clearly defined baseline CV task, its data interface, preprocessing, training, evaluation, checkpointing, qualitative inspection and experiment tracking.

Not allowed: final/advanced model, tissue analysis, longitudinal monitoring, image-quality model, FastAPI, database, frontend, Docker, ONNX/TensorRT optimization, or Phase 03+ work.

## SPEC-02-01 boundary

SPEC-02-01 is the real-data baseline engineering implementation and bounded
sanity gate. It defines validation-only checkpoint selection, reproducibility,
and the Kaggle execution entrypoint. Multi-epoch training and later evaluation
are owned by SPEC-02-02.

SPEC-02-02 does not evaluate the public FUSeg2021 test images as labeled data
because their ground-truth masks are not released.

## Definition of Done

A baseline task is selected and justified; FUSeg2021's official split contract
is verified; preprocessing is reproducible; image/mask transforms are
synchronized; the model and logits-based loss are tested; the Kaggle run,
authorized evaluation, validation-selected checkpoint, structured
reproducibility artifacts, qualitative review, and final baseline record are
complete under SPEC-02-02; relevant tests pass; and no later phase is started.

## Status (2026-10-22)

`COMPLETED`. SPEC-02-01, SPEC-02-02 and SPEC-02-03 are all done.

Held-out FUSeg2021 test results (191 images):
- pooled Dice 0.922
- macro Dice 0.841

Evidence: `reports/experiments/spec_02_03_report.md`.
