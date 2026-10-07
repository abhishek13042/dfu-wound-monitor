# P02-S01 — Baseline Task and Model Selection

## Purpose
Select exactly what Phase 02 will solve and one deliberately simple, defensible baseline model using Phase 01 evidence.

## Inputs
Phase 01 registry, manifests, schema, EDA, annotation visualizations, leakage report and open questions.

## Candidate task
Choose one primary baseline supported by the verified data:
- wound segmentation when suitable wound masks exist;
- wound detection/localization when reliable bounding boxes make that the better first task;
- another task only with explicit evidence.

## Requirements
- **REQ-P02-S01-001:** Record task, dataset, annotation type, input and output.
- **REQ-P02-S01-002:** Compare at least two reasonable baseline approaches on suitability, complexity, compute, interpretability, deployment relevance and limitations.
- **REQ-P02-S01-003:** Do not select a model merely because it is popular.
- **REQ-P02-S01-004:** Baseline must be materially simpler than intended later advanced models.
- **REQ-P02-S01-005:** If pretrained weights are used, record source, weights, frozen/fine-tuned policy and rationale.
- **REQ-P02-S01-006:** Verify labels/annotations/splits support the selected task.
- **REQ-P02-S01-007:** Never use test performance to choose architecture, preprocessing or hyperparameters.

## Required decision record
Problem; dataset; task; input/output; candidates; comparison; selected baseline; rationale; limitations; later improvement path.

## Acceptance
One task and model are explicitly selected, supported by Phase 01 evidence, with no test-set design decisions.
