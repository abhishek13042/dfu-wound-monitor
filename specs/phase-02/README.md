# Phase 02 — Baseline Model

## Purpose
Establish the first reproducible machine-learning baseline for DFU-WoundMonitor. The project master plan requires a baseline before advanced detection/segmentation. The exact baseline must be selected from Phase 01 evidence, not popularity.

## Order
P02-S01 Baseline Task & Model Selection → P02-S02 Preprocessing & Dataset Interface → P02-S03 Baseline Model → P02-S04 Training & Checkpointing → P02-S05 Evaluation → P02-S06 Qualitative Review → P02-S07 Experiment/Reproducibility Report.

## Source-grounded constraints
The master plan allows a simple segmentation model or standard pretrained detection model, says the exact model should be chosen after inspecting the dataset, and explicitly says not to choose YOLO merely because it is popular. Explain model selection. Never fabricate metrics.

## Phase boundary
Allowed: one clearly defined baseline CV task, its data interface, preprocessing, training, evaluation, checkpointing, qualitative inspection and experiment tracking.

Not allowed: final/advanced model, tissue analysis, longitudinal monitoring, image-quality model, FastAPI, database, frontend, Docker, ONNX/TensorRT optimization, or Phase 03+ work.

## Definition of Done
A baseline task is selected and justified; preprocessing is reproducible; model trains; validation is separated from test; actual test metrics are generated; qualitative results are inspected; failures and limitations are documented; experiment/checkpoint provenance is recorded; traceability/tracker are updated; tests pass; no later phase is started.
