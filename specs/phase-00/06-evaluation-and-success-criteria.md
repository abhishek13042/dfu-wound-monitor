# P00-S06 — Evaluation and Success Criteria

## 1. Objective

Define how the system will be measured, compared, tested, and judged successful.

## 2. Scope

Evaluation covers model quality, measurements, longitudinal outputs, image quality, robustness, system behavior, reproducibility, and error analysis.

## 3. Non-Goals

- Inventing target metrics before experiments establish realistic baselines.
- Claiming clinical efficacy from technical metrics.
- Optimizing for a single aggregate metric while ignoring failure cases.

## 4. Requirements

### REQ-P00-S06-001
Every core CV component SHALL have quantitative evaluation metrics appropriate to its task.

### REQ-P00-S06-002
Segmentation evaluation SHALL include overlap metrics such as Dice and IoU.

### REQ-P00-S06-003
Detection evaluation SHALL include appropriate detection metrics and false-positive/false-negative analysis.

### REQ-P00-S06-004
Measurement evaluation SHALL compare predicted image-derived measurements against appropriate reference measurements where available.

### REQ-P00-S06-005
Evaluation SHALL include qualitative visual inspection.

### REQ-P00-S06-006
The project SHALL perform structured error analysis.

### REQ-P00-S06-007
Experiments SHALL record configuration, dataset reference, model information, metrics, and relevant notes.

### REQ-P00-S06-008
No final resume metric SHALL be reported unless it is supported by recorded experimental evidence.

## 5. Assumptions

Appropriate metrics may vary by task and dataset.

## 6. Dependencies

- P00-S02
- P00-S03
- P00-S04
- P00-S05

## 7. Inputs

- Model predictions
- Ground-truth annotations where available
- Measurement references where available
- Experiment metadata

## 8. Outputs

- Evaluation protocol
- Metric definitions
- Experiment records
- Error taxonomy
- Success criteria

## 9. Technical Design

### Detection

Potential metrics:

- Precision
- Recall
- mAP
- IoU
- False positives
- False negatives

### Segmentation

Potential metrics:

- Dice
- IoU
- Precision
- Recall

### Measurement

Evaluation SHALL use an appropriate comparison method depending on whether reference physical measurements or only pixel-level references are available.

### Image Quality

Quality evaluation SHALL assess whether the quality gate correctly identifies unusable/problematic inputs without creating unnecessary rejection.

### Longitudinal

Evaluation SHALL focus on correctness and consistency of image-derived changes and comparisons. Clinical healing claims are outside the technical evaluation scope.

### System

Potential engineering metrics:

- inference latency;
- memory usage;
- API reliability;
- reproducibility;
- end-to-end success rate.

## 10. Implementation Tasks

1. Define metric implementations.
2. Define evaluation datasets/splits.
3. Define experiment record format.
4. Define error-analysis categories.
5. Define final reporting format.

## 11. Risks / Failure Modes

- Metric inflation through data leakage.
- Overfitting to a single dataset.
- Ignoring clinically important failure modes.
- Reporting averages without distribution/worst-case context.
- Comparing incompatible dataset labels.

## 12. Tests / Verification

Evaluation code SHALL be tested on controlled examples where feasible.

Metric implementations SHALL be checked against known/simple cases.

## 13. Acceptance Criteria

- Each core subsystem has defined evaluation metrics.
- Evaluation split strategy is documented.
- Error analysis is required.
- Experiment tracking is defined.
- No unsupported performance target is presented as achieved.

## 14. Evidence

- Evaluation reports
- Metric outputs
- Qualitative prediction grids
- Failure analysis
- Experiment logs

## 15. Reproducibility

Every reported experiment SHALL record:

- dataset/split;
- configuration;
- model/checkpoint;
- preprocessing;
- augmentation;
- seed where applicable;
- metrics;
- environment information.

## 16. Risks / Limitations

Technical metrics do not establish clinical safety or efficacy.

## 17. Traceability

Evaluation requirements SHALL be linked to Phase 02–11 evaluation and acceptance criteria.
