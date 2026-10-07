# P01-S01 — Dataset Source Verification

## Purpose
Establish an auditable record for every dataset considered for DFU-WoundMonitor before it is used. Verify official source, access, license/usage, images, annotations, classes, resolution, splits, patient/examination metadata, and limitations. Clearly distinguish VERIFIED facts, INFERRED engineering conclusions, and UNKNOWN items.

## Candidate datasets
- DFUC2020 — detection/localization role
- DFUC2021 — classification/clinical-label experiment role
- DFUC2022 — wound segmentation role
- DFUTissueSegNet — optional tissue-segmentation role
- newer lower-limb/feet wound dataset — external/generalization or auxiliary role, only after verification

## Requirements
- **REQ-P01-S01-001:** Record authoritative source, publication/reference, repository/download route, and verified version/date where available.
- **REQ-P01-S01-002:** Record actual access status and procedure; do not assume public availability.
- **REQ-P01-S01-003:** Record stated license/usage terms; do not infer redistribution rights.
- **REQ-P01-S01-004:** Record verified image count, formats, dimensions, channels, and official splits where documented.
- **REQ-P01-S01-005:** Record annotation formats, types, classes/labels, boxes, masks, classification/tissue labels, and relevant metadata.
- **REQ-P01-S01-006:** Determine whether patient IDs, examination/visit IDs, or equivalent grouping identifiers exist and whether they support patient-level grouping.
- **REQ-P01-S01-007:** Record documented limitations relevant to acquisition, annotation, imbalance, metadata, intended use, and generalization.
- **REQ-P01-S01-008:** Mark important facts VERIFIED / NOT VERIFIED / INFERRED / UNKNOWN.
- **REQ-P01-S01-009:** Assign a proposed role: primary, auxiliary, external validation/generalization, optional experiment, or rejected, with justification.
- **REQ-P01-S01-010:** A dataset cannot enter project ingestion until source/access/usage status is sufficiently verified and recorded.

## Outputs
Create a dataset registry in human-readable and machine-readable form, plus per-dataset verification records. Preserve source evidence.

## Acceptance
All candidates have verification records; no fabricated facts; patient/exam metadata is explicitly assessed; proposed role is documented; unresolved items are visible.

## Out of scope
No training, CV models, API, database, dashboard, or clinical claims.
