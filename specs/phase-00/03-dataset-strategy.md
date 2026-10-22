# P00-S03 — Dataset Strategy

## 1. Objective

Define how datasets will be selected, verified, combined, split, and used for the different Computer Vision tasks.

## 2. Scope

The project brief identifies candidate datasets including DFUC2020, DFUC2021, DFUC2022, DFUTissueSegNet, and a newer lower-limb/foot wound dataset requiring verification.

Dataset-specific claims SHALL be verified against official sources before implementation.

## 3. Non-Goals

- Downloading datasets during Phase 00.
- Assuming that different datasets share identical annotation semantics.
- Combining datasets without documenting class/annotation differences.
- Assuming patient-level independence when patient identifiers are unavailable.

## 4. Requirements

### REQ-P00-S03-001
Each dataset SHALL have its source, access conditions, license/use conditions, image characteristics, annotation type, classes, split information, and relevant metadata documented before use.

### REQ-P00-S03-002
The project SHALL distinguish verified dataset facts from engineering inferences.

### REQ-P00-S03-003
Patient-level splitting SHALL be used where reliable patient/examination identifiers exist.

### REQ-P00-S03-004
If patient-level identifiers are unavailable, the limitation SHALL be explicitly documented.

### REQ-P00-S03-005
Datasets SHALL be assigned roles based on the task they can validly support.

### REQ-P00-S03-006
Dataset combination SHALL preserve differences in annotation definitions and label semantics.

## 5. Assumptions

Candidate datasets may not contain all labels needed for every stage.

## 6. Dependencies

- P00-S01
- P00-S02

## 7. Inputs

Candidate datasets and their official documentation.

## 8. Outputs

A dataset strategy containing:

- selected datasets;
- role of each dataset;
- task mapping;
- strengths/weaknesses;
- access/license notes;
- split strategy;
- leakage considerations;
- unresolved dataset questions.

## 9. Technical Design

Initial engineering roles:

- DFUC2020: candidate wound detection/localization source.
- DFUC2021: candidate infection/ischemia-related classification experiment where appropriate.
- DFUC2022: candidate primary segmentation source.
- DFUTissueSegNet: candidate tissue-analysis extension.
- Newer lower-limb/foot wound dataset: candidate external/generalization dataset only after verification.

These roles are planning hypotheses until verified against official dataset documentation.

> **Current roles (updated 2026-10-21, after Phase 01 acquisition).** The
> hypotheses above were superseded. DFUC2020/2021/2022 are BLOCKED pending the
> official DFU license application.
>
> - FUSeg2021: primary binary segmentation dataset.
> - LowerLimbFeetWound V3: candidate external evaluation set.
> - Medetec: qualitative out-of-distribution review and quality-gate fixtures. It has no masks.
> - DFUTissueSegNet: optional tissue extension. It shares the AZH source with FUSeg2021.
>
> See `data/external/dataset_registry.json` v2.0.0 and
> `specs/phase-01/OPEN_QUESTIONS.md`.

The project SHALL avoid pretending that separate datasets form a single longitudinal clinical cohort.

## 10. Implementation Tasks

1. Verify official dataset sources.
2. Record access/license information.
3. Record annotation formats and classes.
4. Determine available metadata.
5. Determine whether patient/examination identifiers exist.
6. Map each dataset to a project task.
7. Decide which datasets belong to MVP versus advanced experiments.
8. Document unresolved questions.

## 11. Risks / Failure Modes

- Dataset leakage.
- Different label definitions across datasets.
- Domain shift.
- Annotation-quality differences.
- Different image acquisition conditions.
- Missing patient metadata.
- License/access restrictions.
- False assumption that cross-dataset measurements are directly comparable.

## 12. Tests / Verification

Before acquisition, verify that the documented dataset facts can be traced to an official source or clearly marked as unresolved.

After acquisition, dataset validation will be handled by Phase 01.

## 13. Acceptance Criteria

- Candidate dataset roles are defined.
- Official sources are recorded.
- License/access status is recorded.
- Annotation semantics are documented.
- Patient-level split strategy is documented.
- Cross-dataset limitations are documented.
- No unverified dataset fact is presented as certain.

## 14. Evidence

- Dataset research table
- Official source references
- Dataset decision log
- Leakage assessment

## 15. Reproducibility

Dataset versions/access dates and acquisition instructions SHALL be recorded when Phase 01 is implemented.

## 16. Risks / Limitations

Dataset selection cannot establish clinical validity. External generalization must be evaluated separately.

## 17. Traceability

Each selected dataset SHALL map to one or more downstream Phase 01, Phase 02,
or consolidated Phase 03–06 specifications.
