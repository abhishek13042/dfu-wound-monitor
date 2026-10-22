# P00-S05 — System Architecture

## 1. Objective

Define the architecture and boundaries of the complete DFU-WoundMonitor system before implementation.

## 2. Scope

The architecture covers the CV pipeline, measurement layer, longitudinal layer, API, persistence, dashboard, evaluation, and deployment boundaries.

## 3. Non-Goals

- Finalizing every implementation detail.
- Selecting optimization technologies without benchmark evidence.
- Treating optional tissue analysis as mandatory MVP functionality.

## 4. Requirements

### REQ-P00-S05-001
The architecture SHALL separate image-quality assessment from downstream inference.

### REQ-P00-S05-002
The architecture SHALL allow localization/detection and segmentation components to be evaluated independently.

### REQ-P00-S05-003
Measurement logic SHALL operate on explicit model outputs rather than hidden model internals.

### REQ-P00-S05-004
Examination persistence SHALL be separated from model inference logic.

### REQ-P00-S05-005
Longitudinal comparison SHALL operate on stored examination records.

### REQ-P00-S05-006
Model version information SHALL be associated with inference results.

### REQ-P00-S05-007
The API SHALL provide a stable boundary between application behavior and CV implementation.

### REQ-P00-S05-008
The dashboard SHALL consume application/API outputs rather than directly executing model internals.

## 5. Assumptions

A modular architecture is preferred so that individual models/components can be replaced without rewriting the whole application.

## 6. Dependencies

- P00-S01
- P00-S02
- P00-S04

## 7. Inputs

- Approved requirements
- MVP scope

## 8. Outputs

Architecture description, component responsibilities, and data flow.

## 9. Technical Design

Target conceptual architecture:

```text
                    ┌──────────────────┐
                    │   User / Client  │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │    Dashboard     │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │      API         │
                    └────────┬─────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
     ┌──────────────────┐          ┌─────────────────┐
     │  CV Inference    │          │    Database     │
     │                  │          │                 │
     │ Quality          │          │ Examinations    │
     │ (Localization)*  │          │ Measurements    │
     │ Segmentation     │          │ Model versions  │
     │ Measurement      │          │ History         │
     └────────┬─────────┘          └─────────────────┘
              │
              ▼
     ┌──────────────────┐
     │ Longitudinal     │
     │ Comparison       │
     └──────────────────┘
```

Conceptual CV flow:

```text
Image
  ↓
Quality Assessment
  ↓
[Optional] Localization / Detection *
  ↓
Segmentation (full image by default)
  ↓
Post-processing
  ↓
Measurements
  ↓
Optional Tissue Analysis
```

The exact implementation order may differ where experimentation shows a better design.

\* **Update (2026-10-21):** under `specs/REVISED_ROADMAP.md`, localization and
detection are optional backlog items. Full-image segmentation is the default.
The detection stage is added only when an approved spec shows that it is
needed. Detection datasets (DFUC2020) are also license-blocked.

## 10. Implementation Tasks

1. Finalize component boundaries.
2. Define data contracts.
3. Define model input/output contracts.
4. Define application-to-CV interface.
5. Define examination data boundary.
6. Create architecture documentation/diagram.

## 11. Risks / Failure Modes

- Tight coupling between model and application.
- Hidden preprocessing differences between training and inference.
- Model-version ambiguity.
- Longitudinal logic depending on unversioned results.
- Dashboard directly depending on model internals.

## 12. Tests / Verification

Architecture review SHALL verify that each approved system requirement maps to a component or cross-cutting concern.

## 13. Acceptance Criteria

- End-to-end architecture is documented.
- Component responsibilities are clear.
- Data flow is clear.
- API/CV boundary is clear.
- Persistence boundary is clear.
- Model versioning path is defined.
- MVP and optional components are distinguished.

## 14. Evidence

- Architecture diagram
- Component responsibility table
- Data-flow description
- Approved architecture record

## 15. Reproducibility

Architecture documents SHALL be version controlled with the repository.

## 16. Risks / Limitations

The architecture is an engineering design and may evolve after measured experiments, but changes must be documented rather than silently introduced.

## 17. Traceability

Architecture components SHALL map to system requirements and downstream phase specifications.
