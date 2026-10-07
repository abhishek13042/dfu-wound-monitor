# Phase 01 — Data Foundation

## Goal
Build a trustworthy, reproducible data foundation before serious model development.

## Order
`P01-S01 Source Verification → P01-S02 Ingestion → P01-S03 Quality/Annotation Validation → P01-S04 Schema/Harmonization → P01-S05 Patient-Aware Splits/Manifests → P01-S06 EDA/Visualization`

## Phase boundary
No detection/segmentation model training, FastAPI, database, frontend/dashboard, deployment, or clinical claims in Phase 01.

## Definition of Done
- Dataset sources/access/license are verified.
- Selected datasets are ingested with provenance.
- Raw data is preserved.
- Image/annotation quality is validated.
- Canonical metadata/schema exists without erasing source semantics.
- Patient-aware splits are used where reliable IDs exist.
- Leakage checks pass.
- Reproducible manifests exist.
- EDA and annotation visualizations are generated and inspected.
- Open questions are updated.
- Tests/reproducibility checks pass.
- Traceability and tracker are updated.
- No model-development work has leaked into the phase.

**Engineering principle:** optimize for trustworthy data + traceability + reproducibility + clear evidence, not file count or code volume.
