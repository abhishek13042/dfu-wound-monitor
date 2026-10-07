# P01-S05 — Patient-Aware Splitting and Manifests

## Purpose
Create reproducible train/validation/test manifests while minimizing patient-level leakage.

## Primary rule
When reliable patient identifiers exist: **PATIENT → split**, not **IMAGE → split**. Repeated examinations/visits linked to the same patient must not cross splits.

## Requirements
- **REQ-P01-S05-001:** Use verified patient/examination metadata from earlier specs; do not infer identity without evidence.
- **REQ-P01-S05-002:** Keep all samples from one patient in one split when reliable patient IDs exist.
- **REQ-P01-S05-003:** Prevent linked repeated visits/examinations from crossing splits.
- **REQ-P01-S05-004:** Record a deterministic random seed when randomness is used.
- **REQ-P01-S05-005:** Record split ratios/counts, seed, grouping, stratification rule if any, dataset/version, and manifest version.
- **REQ-P01-S05-006:** Class balancing/stratification must never override patient grouping; document unavoidable imbalance.
- **REQ-P01-S05-007:** Check duplicate checksums, repeated patient IDs, repeated exam IDs, and identifiable source duplicates across splits.
- **REQ-P01-S05-008:** If reliable patient IDs are absent, explicitly state the limitation, do not claim patient-level leakage prevention, and document any fallback split.
- **REQ-P01-S05-009:** Keep datasets designated for external/generalization evaluation isolated from model-development training unless a later specification approves otherwise.
- **REQ-P01-S05-010:** Manifest supports `sample_id`, dataset/version, image/annotation paths, checksum, patient/exam IDs, split, annotation type, and validation status.
- **REQ-P01-S05-011:** Same verified inputs and split configuration reproduce the same assignment.

## Acceptance
Every usable sample has a split or explicit exclusion reason; grouping/leakage checks pass; seed/configuration is recorded; missing-ID limitations are explicit; manifests are deterministic and machine-readable.

## Out of scope
Training, test-set tuning, clinical generalization claims.
