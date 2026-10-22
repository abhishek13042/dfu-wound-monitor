# P00-S07 — Risks, Limitations and Phase Acceptance

## 1. Objective

Establish the project's major risks, known limitations, open technical questions, and the conditions required to complete Phase 00.

## 2. Scope

This specification covers risks that affect dataset validity, model performance, longitudinal interpretation, engineering reliability, and medical positioning.

## 3. Non-Goals

This document does not attempt to eliminate all project risks before implementation.

## 4. Requirements

### REQ-P00-S07-001
Known dataset limitations SHALL be documented.

### REQ-P00-S07-002
Patient-level leakage risk SHALL be explicitly assessed.

### REQ-P00-S07-003
Domain shift and acquisition variation SHALL be considered.

### REQ-P00-S07-004
Image-quality variation SHALL be considered.

### REQ-P00-S07-005
Annotation uncertainty/quality SHALL be considered.

### REQ-P00-S07-006
Measurement limitations SHALL be documented.

### REQ-P00-S07-007
Longitudinal comparisons SHALL be presented with their data limitations.

### REQ-P00-S07-008
Clinical limitations SHALL be visible in project documentation.

### REQ-P00-S07-009
Open questions SHALL be tracked rather than silently assumed.

## 5. Assumptions

Risks can be reduced through experiments and engineering controls, but cannot all be eliminated through software design alone.

## 6. Dependencies

- All other Phase 00 specifications

## 7. Inputs

- Project definition
- Scope
- Dataset strategy
- Requirements
- Architecture
- Evaluation strategy

## 8. Outputs

- Risk register
- Limitations register
- Phase 00 acceptance checklist
- Open questions

## 9. Technical Design

Initial risk categories:

| Category | Example Risk |
|---|---|
| Data | Dataset leakage |
| Data | Annotation inconsistency |
| Generalization | Camera/domain shift |
| Image | Blur/lighting/occlusion |
| Model | False negatives |
| Segmentation | Boundary errors |
| Measurement | Lack of physical scale |
| Longitudinal | Inconsistent acquisition conditions |
| Engineering | Model/version mismatch |
| Medical | Unsupported clinical interpretation |

## 10. Implementation Tasks

1. Create risk register.
2. Link major risks to downstream mitigations.
3. Review medical limitations.
4. Review dataset leakage limitations.
5. Review open questions.
6. Conduct Phase 00 gate review.

## 11. Risks / Failure Modes

The risks listed above are themselves project risks and SHALL be revisited as evidence becomes available.

## 12. Tests / Verification

Phase 00 review SHALL verify that:

- scope is defined;
- datasets have a documented strategy;
- architecture is coherent;
- requirements are testable;
- evaluation is defined;
- risks and limitations are explicit.

## 13. Acceptance Criteria

### Phase 00 is COMPLETE only when:

- [x] P00-S01 approved
- [x] P00-S02 approved
- [x] P00-S03 approved
- [x] P00-S04 approved
- [x] P00-S05 approved
- [x] P00-S06 approved
- [x] P00-S07 approved
- [x] Open questions are explicitly recorded
- [x] Master tracker is updated
- [x] Traceability structure exists
- [x] No unresolved critical ambiguity blocks Phase 01

Gate record:

- Phase 00 is marked COMPLETED in `specs/MASTER_TRACKER.md`.
- The integrity checks are in `tests/unit/test_phase_00_integrity.py`.
- Boxes were ticked on 2026-10-21 to match the tracker.

## 14. Evidence

- Approved Phase 00 specifications
- Risk register
- Open-question register
- Phase gate record

## 15. Reproducibility

Phase 00 decisions SHALL be version controlled.

## 16. Risks / Limitations

Phase acceptance means the project is sufficiently specified to begin dataset engineering. It does not mean that the resulting models are accurate, clinically validated, or deployment-ready.

## 17. Traceability

The Phase 00 gate SHALL reference all seven Phase 00 specifications and their approval status.
