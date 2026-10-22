# DFU-WoundMonitor — Master Specification Tracker

## Project Status

**Phase:** Phase 06 — System Validation & Release (all planned phases complete)  
**Overall Status:** Phases 00–06 COMPLETED. Model: held-out pooled Dice 0.922, macro 0.841 (independently verified). Service, dashboard, validation, benchmark and release are in `reports/final/` and `docs/release/RELEASE.md`. One partial item: REQ-P06-S03-001 fresh-machine install was not exercised.

---

## Phase Overview

| Phase | Name | Specs | Completed | Status |
|---|---|---|---|---|
| phase-00 | Project Definition & System Specification | 7 | 7 | COMPLETED |
| phase-01 | Dataset & Data Engineering | 6 | 6 | COMPLETED |
| phase-02 | Baseline Segmentation Completion | 3 active specs | 3 | COMPLETED |
| phase-03 | Core CV Inference & Measurements | 3 | 3 | COMPLETED |
| phase-04 | Longitudinal Wound-Monitoring Workflow | 3 | 3 | COMPLETED |
| phase-05 | Product Integration | 3 | 3 | COMPLETED |
| phase-06 | System Validation & Release | 3 | 3 | COMPLETED |
| phase-07–12 | Legacy granular roadmap (folders removed) | Replaced | 0 | DEFERRED — mapped into phases 03–06 |

---

## Specification Tracking

| Spec ID | Phase | Specification | Status | Dependencies | Evidence |
|---|---|---|---|---|---|
| P00-S01 | phase-00 | Project Definition | COMPLETED | None | specs/phase-00/01-project-definition.md |
| P00-S02 | phase-00 | Scope and MVP | COMPLETED | P00-S01 | specs/phase-00/02-scope-and-mvp.md |
| P00-S03 | phase-00 | Dataset Strategy | COMPLETED | P00-S01, P00-S02 | specs/phase-00/03-dataset-strategy.md |
| P00-S04 | phase-00 | System Requirements | COMPLETED | P00-S01, P00-S02, P00-S03 | specs/phase-00/04-system-requirements.md |
| P00-S05 | phase-00 | System Architecture | COMPLETED | P00-S01, P00-S02, P00-S04 | specs/phase-00/05-system-architecture.md, docs/architecture/system-architecture.md |
| P00-S06 | phase-00 | Evaluation and Success Criteria | COMPLETED | P00-S02, P00-S03, P00-S04, P00-S05 | specs/phase-00/06-evaluation-and-success-criteria.md |
| P00-S07 | phase-00 | Risks, Limitations and Phase Acceptance | COMPLETED | P00-S01..P00-S06 | specs/phase-00/07-risks-limitations-and-acceptance.md, tests/unit/test_phase_00_integrity.py |
| P01-S01 | phase-01 | Dataset Source Verification | COMPLETED | P00-S03 | data/external/dataset_registry.json, reports/dataset_verification_report.md |
| P01-S02 | phase-01 | Data Ingestion and Organization | COMPLETED | P01-S01 | src/data/ingestion.py, reports/ingestion_report.json |
| P01-S03 | phase-01 | Data Quality and Annotation Validation | COMPLETED | P01-S02 | src/data/validation.py, data/manifests/quality_validation_report.json |
| P01-S04 | phase-01 | Dataset Schema and Label Harmonization | COMPLETED | P01-S03 | src/data/schema.py |
| P01-S05 | phase-01 | Patient-Aware Splitting and Manifests | COMPLETED | P01-S04 | src/data/splitting.py, data/manifests/dataset_manifest.json |
| P01-S06 | phase-01 | EDA and Annotation Visualization | COMPLETED | P01-S05 | src/data/eda.py, outputs/visualizations/phase_01_annotation_grid.png, reports/eda_summary.json |
| P02-S01 | phase-02 | Baseline Task and Model Selection | COMPLETED | P01-S06 | reports/experiments/phase_02_baseline_decision_record.md |
| P02-S02 | phase-02 | Preprocessing and Dataset Interface | COMPLETED | P02-S01 | src/segmentation/dataset.py, configs/data/fuseg2021.json |
| P02-S03 | phase-02 | Baseline Model Implementation | COMPLETED | P02-S01, P02-S02 | src/segmentation/model.py, tests/unit/test_phase_02_baseline.py |
| SPEC-02-01 | phase-02 | Baseline Engineering Implementation (consolidates P02-S01..S03) | COMPLETED | P01-S06 | specs/phase-02/SPEC-02-01-baseline-engineering.md, reports/experiments/P02-SPEC-02-01-fuseg2021_sanity_checks.json |
| P02-S04 | phase-02 | Baseline Training and Checkpointing | COMPLETED via SPEC-02-02/03 | P02-S03 | scripts/run_spec_02_03.py, reports/experiments/spec-02-03/kaggle/spec-02-03/training_log.json |
| P02-S05 | phase-02 | Baseline Evaluation and Metrics | COMPLETED via SPEC-02-02/03 | P02-S04 | heldout_test_evaluation.json, reports/experiments/spec-02-03/cpu_verification/ |
| P02-S06 | phase-02 | Qualitative Evaluation and Error Review | COMPLETED via SPEC-02-02/03 | P02-S05 | reports/experiments/spec_02_03_report.md §4, reports/figures/spec-02-03/ |
| P02-S07 | phase-02 | Experiment Reproducibility and Baseline Report | COMPLETED via SPEC-02-02/03 | P02-S06 | reports/experiments/spec_02_03_report.md. The `P02-baseline-unet-bce-dice-v1_*` files are the historical **synthetic** run, not evidence. |

## Consolidated Future Specification Tracker

The detailed scope, requirements, dependencies, and gates are maintained in
`specs/REVISED_ROADMAP.md`. Individual specification files must be authored
from `specs/SPEC_TEMPLATE.md` before implementation begins.

| Spec ID | Capability | Status | Dependencies | Specification |
|---|---|---|---|---|
| SPEC-02-02 | Baseline run, authorized evaluation, error review, and final baseline record | COMPLETED (executed by SPEC-02-03) | SPEC-02-01 | `specs/phase-02/SPEC-02-02-baseline-completion.md` |
| SPEC-02-03 | Pretrained ResNet34 U-Net, held-out split, native-resolution evaluation, LowerLimb external check | COMPLETED (2026-10-22) | SPEC-02-01 | `specs/phase-02/SPEC-02-03-strong-segmentation.md` |
| P03-S01 | Inference and model artifact contract | COMPLETED | SPEC-02-03 | `specs/phase-03/01-inference-and-model-contract.md` |
| P03-S02 | Image quality gate | COMPLETED | P03-S01 | `specs/phase-03/02-image-quality-gate.md` |
| P03-S03 | Wound measurement engine | COMPLETED | P03-S01 | `specs/phase-03/03-measurement-engine.md` |
| P04-S01 | Examination and case data contract | COMPLETED | P03-S01, P03-S03 | `specs/phase-04/01-examination-data-contract.md` |
| P04-S02 | Multi-examination alignment and comparison | COMPLETED | P04-S01 | `specs/phase-04/02-examination-comparison.md` |
| P04-S03 | Trajectory and technical trend outputs | COMPLETED | P04-S02 | `specs/phase-04/03-technical-trends.md` |
| P05-S01 | Inference API contract | COMPLETED | P03-S01, P03-S02, P03-S03 | `specs/phase-05/01-inference-api.md` |
| P05-S02 | Persistence and model-result storage | COMPLETED | P04-S01, P05-S01 | `specs/phase-05/02-persistence-and-results.md` |
| P05-S03 | Minimal monitoring dashboard | COMPLETED | P04-S03, P05-S01, P05-S02 | `specs/phase-05/03-minimal-dashboard.md` |
| P06-S01 | End-to-end validation and error analysis | COMPLETED | P05-S03 | `specs/phase-06/01-end-to-end-validation.md` |
| P06-S02 | Reliability, reproducibility, and performance | COMPLETED | P06-S01 | `specs/phase-06/02-reliability-and-performance.md` |
| P06-S03 | Deployment and portfolio release | COMPLETED | P06-S02 | `specs/phase-06/03-deployment-and-release.md` |

The former phase-03 through phase-12 entries are retained only as historical
planning references; they are no longer independent execution gates.
