# P00-S02 — Scope and MVP

## 1. Objective

Define the minimum complete system and separate it from advanced capabilities so that implementation remains focused.

## 2. Scope

### MVP

The MVP SHALL aim to demonstrate:

1. Validated dataset pipeline.
2. Wound localization/detection where required.
3. Wound segmentation.
4. Image-derived wound measurements.
5. Image quality assessment.
6. Examination record representation.
7. Longitudinal comparison of available examinations.
8. Reproducible evaluation.
9. API access to the inference workflow.
10. A basic dashboard demonstrating the end-to-end workflow.

### Advanced / Optional

Potential advanced capabilities include:

- tissue analysis;
- additional external-dataset generalization;
- uncertainty estimation;
- stronger robustness experiments;
- ONNX/TensorRT optimization where benchmarks justify it;
- expanded model/version management;
- additional deployment infrastructure.

Advanced capabilities SHALL NOT silently become MVP requirements.

## 3. Non-Goals

- Building every possible medical-AI capability.
- Adding technologies solely to make the stack appear complex.
- Optimizing inference before correctness and evaluation are established.
- Treating every optional dataset as mandatory.

## 4. Requirements

### REQ-P00-S02-001
The MVP SHALL represent a complete user-facing workflow rather than only an isolated model.

### REQ-P00-S02-002
Every MVP capability SHALL have a corresponding evaluation or verification strategy.

### REQ-P00-S02-003
Optional capabilities SHALL be explicitly labeled as optional or advanced.

### REQ-P00-S02-004
MVP scope SHALL prioritize measurable Computer Vision value and reproducibility.

## 5. Assumptions

The MVP may use separate datasets for different CV tasks if no single dataset supports the complete pipeline.

## 6. Dependencies

- P00-S01

## 7. Inputs

- Project definition
- Candidate datasets
- Engineering constraints

## 8. Outputs

- MVP feature list
- Advanced feature list
- Explicit scope boundaries
- Dependency-aware implementation roadmap

## 9. Technical Design

MVP priority order:

1. Data correctness
2. Baseline CV capability
3. Stronger CV model
4. Quantitative outputs
5. Longitudinal engineering workflow
6. Application integration
7. Evaluation and error analysis
8. Deployment/reproducibility

## 10. Implementation Tasks

1. Review every proposed project capability.
2. Assign MVP or Advanced status.
3. Record dependencies.
4. Identify capabilities that can be deferred without breaking the MVP.
5. Update the master tracker after approval.

## 11. Risks / Failure Modes

- Feature creep.
- Over-investment in frontend before model quality is understood.
- Adding advanced optimization without a performance bottleneck.
- Attempting clinical claims from engineering outputs.

## 12. Tests / Verification

Perform a scope review: removing an advanced feature must not make the MVP incomplete.

## 13. Acceptance Criteria

- MVP is finite and understandable.
- Advanced scope is explicitly separated.
- No capability is included without a reason.
- Dependencies are documented.
- MVP can be evaluated end-to-end.

## 14. Evidence

- Approved scope table
- MVP/Advanced decision log

## 15. Reproducibility

Record the approved scope version/date in the project tracker.

## 16. Risks / Limitations

MVP scope does not imply clinical readiness.

## 17. Traceability

Every MVP capability SHALL map to at least one later specification.
