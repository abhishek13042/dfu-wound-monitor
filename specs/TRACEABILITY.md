# Requirements Traceability Matrix

## Traceability Chain

The project enforces an unbroken chain of traceability from requirement to acceptance:

```
Requirement
    ↓
Specification
    ↓
Implementation
    ↓
Test
    ↓
Evidence
    ↓
Acceptance
```

1. **Requirement**: Precise, verifiable statement of capability or constraint (`REQ-PXX-SXX-XXX`).
2. **Specification**: Engineering document detailing technical design and tasks (`PXX-SXX`).
3. **Implementation**: Code modules, architecture contracts, and documentation artifacts fulfilling the requirements.
4. **Test**: Automated verification scripts and manual gate review checks verifying compliance.
5. **Evidence**: Artifacts, execution logs, reports, or test suite outputs demonstrating completion.
6. **Acceptance**: Sign-off criteria met according to the Definition of Done.

---

## Traceability Matrix

### Phase 00 Requirements

| Requirement ID | Spec ID | Implementation / Artifact | Test / Validation | Evidence | Status |
|---|---|---|---|---|---|
| REQ-P00-S01-001 | P00-S01 | specs/phase-00/01-project-definition.md | Structural review of workflow | Phase 00 Gate Checklist | COMPLETED |
| REQ-P00-S01-002 | P00-S01 | README.md & docs/architecture/system-architecture.md | Medical boundary audit | README Medical Disclaimer | COMPLETED |
| REQ-P00-S01-003 | P00-S01 | docs/architecture/system-architecture.md | Schema & architecture check | System Architecture Doc | COMPLETED |
| REQ-P00-S01-004 | P00-S01 | README.md & specs/phase-00/01-project-definition.md | Limitation documentation audit | Project Definition & README | COMPLETED |
| REQ-P00-S02-001 | P00-S02 | specs/phase-00/02-scope-and-mvp.md | MVP feature list verification | Scope & MVP Spec | COMPLETED |
| REQ-P00-S02-002 | P00-S02 | specs/phase-00/06-evaluation-and-success-criteria.md | Verification protocol audit | Evaluation Spec | COMPLETED |
| REQ-P00-S02-003 | P00-S02 | specs/phase-00/02-scope-and-mvp.md | Scope taxonomy check | Scope & MVP Spec | COMPLETED |
| REQ-P00-S02-004 | P00-S02 | specs/phase-00/02-scope-and-mvp.md & Makefile | Build & test pipeline check | Makefile & MVP Spec | COMPLETED |
| REQ-P00-S03-001 | P00-S03 | specs/phase-00/03-dataset-strategy.md | Dataset metadata checklist | Dataset Strategy Spec | COMPLETED |
| REQ-P00-S03-002 | P00-S03 | specs/phase-00/03-dataset-strategy.md | Provenance verification | Dataset Strategy Spec | COMPLETED |
| REQ-P00-S03-003 | P00-S03 | specs/phase-00/03-dataset-strategy.md | Split strategy review | Dataset Strategy Spec | COMPLETED |
| REQ-P00-S03-004 | P00-S03 | specs/phase-00/07-risks-limitations-and-acceptance.md | Leakage assessment audit | Risk Register | COMPLETED |
| REQ-P00-S03-005 | P00-S03 | specs/phase-00/03-dataset-strategy.md | Task mapping check | Dataset Strategy Spec | COMPLETED |
| REQ-P00-S03-006 | P00-S03 | specs/phase-00/03-dataset-strategy.md | Label semantics audit | Dataset Strategy Spec | COMPLETED |
| REQ-P00-S04-001 | P00-S04 | src/data/__init__.py & docs/architecture/system-architecture.md | Module boundary check | System Architecture Doc | COMPLETED |
| REQ-P00-S04-002 | P00-S04 | docs/architecture/system-architecture.md | Quality gate design check | System Architecture Doc | COMPLETED |
| REQ-P00-S04-003 | P00-S04 | src/quality/__init__.py & docs/architecture/system-architecture.md | Quality module architecture check | System Architecture Doc | COMPLETED |
| REQ-P00-S04-004 | P00-S04 | docs/architecture/system-architecture.md | Error handling specification | System Architecture Doc | COMPLETED |
| REQ-P00-S04-005 | P00-S04 | docs/architecture/system-architecture.md (optional stage; empty package removed 2026-10-30) | Detection module boundary check | System Architecture Doc | COMPLETED |
| REQ-P00-S04-006 | P00-S04 | docs/architecture/system-architecture.md | Bounding box schema check | System Architecture Doc | COMPLETED |
| REQ-P00-S04-007 | P00-S04 | src/segmentation/__init__.py & docs/architecture/system-architecture.md | Segmentation module boundary check | System Architecture Doc | COMPLETED |
| REQ-P00-S04-008 | P00-S04 | specs/phase-00/06-evaluation-and-success-criteria.md | Metric protocol review | Evaluation Spec | COMPLETED |
| REQ-P00-S04-009 | P00-S04 | src/measurement/__init__.py & docs/architecture/system-architecture.md | Measurement module boundary check | System Architecture Doc | COMPLETED |
| REQ-P00-S04-010 | P00-S04 | docs/architecture/system-architecture.md | Calibration flag check | System Architecture Doc | COMPLETED |
| REQ-P00-S04-011 | P00-S04 | docs/architecture/system-architecture.md | Schema design check | System Architecture Doc | COMPLETED |
| REQ-P00-S04-012 | P00-S04 | docs/architecture/system-architecture.md | Record provenance check | System Architecture Doc | COMPLETED |
| REQ-P00-S04-013 | P00-S04 | src/longitudinal/__init__.py & docs/architecture/system-architecture.md | Longitudinal boundary check | System Architecture Doc | COMPLETED |
| REQ-P00-S04-014 | P00-S04 | specs/phase-00/01-project-definition.md & README.md | Clinical boundary audit | README Disclaimer | COMPLETED |
| REQ-P00-S04-015 | P00-S04 | src/api/ & docs/architecture/system-architecture.md | API layer layout check | API package layout | COMPLETED |
| REQ-P00-S04-016 | P00-S04 | docs/architecture/system-architecture.md | Error handling specification | System Architecture Doc | COMPLETED |
| REQ-P00-S04-017 | P00-S04 | src/storage/database.py & docs/architecture/system-architecture.md | Database architecture review | Storage module | COMPLETED |
| REQ-P00-S04-018 | P00-S04 | docs/architecture/system-architecture.md | Model versioning contract | System Architecture Doc | COMPLETED |
| REQ-P00-S04-019 | P00-S04 | src/dashboard/index.html & docs/architecture/system-architecture.md | Frontend dashboard design check | Dashboard source | COMPLETED |
| REQ-P00-S04-020 | P00-S04 | docs/development/EXPERIMENTS.md | Experiment tracking rules | Experiment record guide | COMPLETED |
| REQ-P00-S04-021 | P00-S04 | tests/ & scripts/verification/verify_phase_00.py | Integrity test execution | Test Execution Output | COMPLETED |
| REQ-P00-S04-022 | P00-S04 | docker/README.md & README.md | Deployment structure review | Docker README | COMPLETED |
| REQ-P00-S05-001 | P00-S05 | docs/architecture/system-architecture.md | Pipeline separation check | System Architecture Doc | COMPLETED |
| REQ-P00-S05-002 | P00-S05 | docs/architecture/system-architecture.md | Component decoupling check | System Architecture Doc | COMPLETED |
| REQ-P00-S05-003 | P00-S05 | docs/architecture/system-architecture.md | Measurement interface check | System Architecture Doc | COMPLETED |
| REQ-P00-S05-004 | P00-S05 | docs/architecture/system-architecture.md | Persistence separation check | System Architecture Doc | COMPLETED |
| REQ-P00-S05-005 | P00-S05 | docs/architecture/system-architecture.md | Longitudinal data flow check | System Architecture Doc | COMPLETED |
| REQ-P00-S05-006 | P00-S05 | docs/architecture/system-architecture.md | Model metadata contract | System Architecture Doc | COMPLETED |
| REQ-P00-S05-007 | P00-S05 | docs/architecture/system-architecture.md | API boundary check | System Architecture Doc | COMPLETED |
| REQ-P00-S05-008 | P00-S05 | docs/architecture/system-architecture.md | Dashboard interaction check | System Architecture Doc | COMPLETED |
| REQ-P00-S06-001 | P00-S06 | specs/phase-00/06-evaluation-and-success-criteria.md | Quantitative metric check | Evaluation Spec | COMPLETED |
| REQ-P00-S06-002 | P00-S06 | specs/phase-00/06-evaluation-and-success-criteria.md | Dice/IoU definition check | Evaluation Spec | COMPLETED |
| REQ-P00-S06-003 | P00-S06 | specs/phase-00/06-evaluation-and-success-criteria.md | Detection evaluation protocol | Evaluation Spec | COMPLETED |
| REQ-P00-S06-004 | P00-S06 | specs/phase-00/06-evaluation-and-success-criteria.md | Measurement evaluation design | Evaluation Spec | COMPLETED |
| REQ-P00-S06-005 | P00-S06 | specs/phase-00/06-evaluation-and-success-criteria.md | Visual inspection protocol | Evaluation Spec | COMPLETED |
| REQ-P00-S06-006 | P00-S06 | specs/phase-00/06-evaluation-and-success-criteria.md | Error taxonomy definition | Evaluation Spec | COMPLETED |
| REQ-P00-S06-007 | P00-S06 | docs/development/EXPERIMENTS.md | Experiment logging format | Experiment record guide | COMPLETED |
| REQ-P00-S06-008 | P00-S06 | specs/phase-00/06-evaluation-and-success-criteria.md | Metric reporting policy check | Evaluation Spec | COMPLETED |
| REQ-P00-S07-001 | P00-S07 | specs/phase-00/07-risks-limitations-and-acceptance.md | Limitation register audit | Risk Register | COMPLETED |
| REQ-P00-S07-002 | P00-S07 | specs/phase-00/07-risks-limitations-and-acceptance.md | Leakage risk assessment | Risk Register | COMPLETED |
| REQ-P00-S07-003 | P00-S07 | specs/phase-00/07-risks-limitations-and-acceptance.md | Domain shift analysis | Risk Register | COMPLETED |
| REQ-P00-S07-004 | P00-S07 | specs/phase-00/07-risks-limitations-and-acceptance.md | Image quality risk assessment | Risk Register | COMPLETED |
| REQ-P00-S07-005 | P00-S07 | specs/phase-00/07-risks-limitations-and-acceptance.md | Annotation quality assessment | Risk Register | COMPLETED |
| REQ-P00-S07-006 | P00-S07 | specs/phase-00/07-risks-limitations-and-acceptance.md | Measurement limitation register | Risk Register | COMPLETED |
| REQ-P00-S07-007 | P00-S07 | specs/phase-00/07-risks-limitations-and-acceptance.md | Longitudinal limitation audit | Risk Register | COMPLETED |
| REQ-P00-S07-008 | P00-S07 | README.md & specs/phase-00/07-risks-limitations-and-acceptance.md | Medical disclaimer check | README & Risk Register | COMPLETED |
| REQ-P00-S07-009 | P00-S07 | specs/phase-00/OPEN_QUESTIONS.md | Open question tracking check | Open Questions Doc | COMPLETED |

### Phase 01 Requirements

| Requirement ID | Spec ID | Implementation / Artifact | Test / Validation | Evidence | Status |
|---|---|---|---|---|---|
| REQ-P01-S01-001 | P01-S01 | data/external/dataset_registry.json | test_p01_s01_dataset_registry_integrity | reports/dataset_verification_report.md | COMPLETED |
| REQ-P01-S01-002 | P01-S01 | data/external/dataset_registry.json | Registry validation check | dataset_registry.json | COMPLETED |
| REQ-P01-S01-003 | P01-S01 | reports/dataset_verification_report.md | License term audit | dataset_verification_report.md | COMPLETED |
| REQ-P01-S01-004 | P01-S01 | reports/dataset_verification_report.md | Image count verification | dataset_verification_report.md | COMPLETED |
| REQ-P01-S01-005 | P01-S01 | data/external/dataset_registry.json | Annotation schema check | dataset_registry.json | COMPLETED |
| REQ-P01-S01-006 | P01-S01 | reports/dataset_verification_report.md | Metadata privacy audit | dataset_verification_report.md | COMPLETED |
| REQ-P01-S01-007 | P01-S01 | reports/dataset_verification_report.md | Limitation register check | dataset_verification_report.md | COMPLETED |
| REQ-P01-S01-008 | P01-S01 | data/external/dataset_registry.json | Verification taxonomy check | dataset_registry.json | COMPLETED |
| REQ-P01-S01-009 | P01-S01 | reports/dataset_verification_report.md | Proposed role audit | dataset_verification_report.md | COMPLETED |
| REQ-P01-S01-010 | P01-S01 | scripts/data/run_phase_01_pipeline.py | Ingestion gateway check | pipeline output | COMPLETED |
| REQ-P01-S02-001 | P01-S02 | src/data/ingestion.py | Filter verification | reports/ingestion_report.json | COMPLETED |
| REQ-P01-S02-002 | P01-S02 | src/data/ingestion.py | Immutability audit | data/raw/ storage layer | COMPLETED |
| REQ-P01-S02-003 | P01-S02 | src/data/ingestion.py | Provenance tracking check | reports/ingestion_report.json | COMPLETED |
| REQ-P01-S02-004 | P01-S02 | src/data/ingestion.py | test_p01_s02_checksum_determinism | checksum output | COMPLETED |
| REQ-P01-S02-005 | P01-S02 | src/data/ingestion.py | Sorted directory scan check | ingestion log | COMPLETED |
| REQ-P01-S02-006 | P01-S02 | src/data/ingestion.py | Format detection test | ingestion report | COMPLETED |
| REQ-P01-S02-007 | P01-S02 | reports/ingestion_report.json | Ingestion report validation | reports/ingestion_report.json | COMPLETED |
| REQ-P01-S02-008 | P01-S02 | src/data/ingestion.py | Re-entrancy execution check | test output | COMPLETED |
| REQ-P01-S02-009 | P01-S02 | src/data/ingestion.py | Transformation audit | data/raw/ integrity | COMPLETED |
| REQ-P01-S02-010 | P01-S02 | src/data/ingestion.py | Config parameter check | ingestion settings | COMPLETED |
| REQ-P01-S03-001 | P01-S03 | src/data/validation.py | PIL decoding test | quality_validation_report.json | COMPLETED |
| REQ-P01-S03-002 | P01-S03 | src/data/validation.py | Image metadata check | quality_validation_report.json | COMPLETED |
| REQ-P01-S03-003 | P01-S03 | src/data/validation.py | Annotation parse test | quality_validation_report.json | COMPLETED |
| REQ-P01-S03-004 | P01-S03 | src/data/validation.py | test_p01_s03_bounding_box_validation | unittest output | COMPLETED |
| REQ-P01-S03-005 | P01-S03 | src/data/validation.py | Mask dimension/value check | quality_validation_report.json | COMPLETED |
| REQ-P01-S03-006 | P01-S03 | src/data/validation.py | Missing annotation test | quality_validation_report.json | COMPLETED |
| REQ-P01-S03-007 | P01-S03 | src/data/validation.py | Checksum duplicate test | quality_validation_report.json | COMPLETED |
| REQ-P01-S03-008 | P01-S03 | src/data/validation.py | Issue taxonomy categorization | quality_validation_report.json | COMPLETED |
| REQ-P01-S03-009 | P01-S03 | src/data/validation.py | Quarantine list check | quality_validation_report.json | COMPLETED |
| REQ-P01-S03-010 | P01-S03 | data/manifests/quality_validation_report.json | Machine report validation | quality_validation_report.json | COMPLETED |
| REQ-P01-S03-011 | P01-S03 | data/manifests/quality_validation_report.json | Summary validation check | quality_validation_report.json | COMPLETED |
| REQ-P01-S04-001 | P01-S04 | src/data/schema.py | Canonical metadata audit | dataset_manifest.json | COMPLETED |
| REQ-P01-S04-002 | P01-S04 | src/data/schema.py | Original label preservation | dataset_manifest.json | COMPLETED |
| REQ-P01-S04-003 | P01-S04 | src/data/schema.py | test_p01_s04_label_harmonization | unittest output | COMPLETED |
| REQ-P01-S04-004 | P01-S04 | src/data/schema.py | Semantic compatibility check | LABEL_MAPPING_REGISTRY | COMPLETED |
| REQ-P01-S04-005 | P01-S04 | src/data/schema.py | Task separation check | LABEL_MAPPING_REGISTRY | COMPLETED |
| REQ-P01-S04-006 | P01-S04 | src/data/validation.py | Bounding box convention check | [x_min, y_min, x_max, y_max] | COMPLETED |
| REQ-P01-S04-007 | P01-S04 | src/data/validation.py | Mask convention check | (Height x Width, 0/255) | COMPLETED |
| REQ-P01-S04-008 | P01-S04 | src/data/schema.py | Metadata non-fabrication check | NULL/UNKNOWN values | COMPLETED |
| REQ-P01-S04-009 | P01-S04 | src/data/schema.py | Independent schema review | dataset_manifest.json | COMPLETED |
| REQ-P01-S04-010 | P01-S04 | src/data/schema.py | Canonical field validation | dataset_manifest.json | COMPLETED |
| REQ-P01-S05-001 | P01-S05 | src/data/splitting.py | Verified metadata check | dataset_manifest.json | COMPLETED |
| REQ-P01-S05-002 | P01-S05 | src/data/splitting.py | test_p01_s05_patient_aware_splitting_and_leakage | Group-K-Fold test | COMPLETED |
| REQ-P01-S05-003 | P01-S05 | src/data/splitting.py | Repeat visit leakage test | leakage report | COMPLETED |
| REQ-P01-S05-004 | P01-S05 | src/data/splitting.py | Seed reproducibility test | seed=42 check | COMPLETED |
| REQ-P01-S05-005 | P01-S05 | data/manifests/dataset_manifest.json | Split summary validation | dataset_manifest.json | COMPLETED |
| REQ-P01-S05-006 | P01-S05 | src/data/splitting.py | Patient priority check | split summary | COMPLETED |
| REQ-P01-S05-007 | P01-S05 | src/data/splitting.py | Leakage verification suite | dataset_manifest.json | COMPLETED |
| REQ-P01-S05-008 | P01-S05 | src/data/splitting.py | Fallback limitation record | split_summary limitation note | COMPLETED |
| REQ-P01-S05-009 | P01-S05 | data/external/dataset_registry.json | External dataset isolation check | FUSeg2021 registry role | COMPLETED |
| REQ-P01-S05-010 | P01-S05 | data/manifests/dataset_manifest.json | Manifest field schema audit | dataset_manifest.json | COMPLETED |
| REQ-P01-S05-011 | P01-S05 | src/data/splitting.py | Deterministic rerun test | manifest checksum | COMPLETED |
| REQ-P01-S06-001 | P01-S06 | reports/eda_summary.json | Image stat summary check | eda_summary.json | COMPLETED |
| REQ-P01-S06-002 | P01-S06 | reports/eda_summary.json | Dimension/aspect ratio stats | eda_summary.json | COMPLETED |
| REQ-P01-S06-003 | P01-S06 | src/data/eda.py | Bounding box EDA module | eda_summary.json | COMPLETED |
| REQ-P01-S06-004 | P01-S06 | reports/eda_summary.json | Mask area ratio stats | eda_summary.json | COMPLETED |
| REQ-P01-S06-005 | P01-S06 | reports/eda_summary.json | Patient/exam metadata audit | eda_summary.json | COMPLETED |
| REQ-P01-S06-006 | P01-S06 | reports/eda_summary.json | Split distribution comparison | eda_summary.json | COMPLETED |
| REQ-P01-S06-007 | P01-S06 | src/data/eda.py | Segmentation overlay renderer | phase_01_annotation_grid.png | COMPLETED |
| REQ-P01-S06-008 | P01-S06 | outputs/visualizations/phase_01_annotation_grid.png | Visualization grid check | phase_01_annotation_grid.png | COMPLETED |
| REQ-P01-S06-009 | P01-S06 | scripts/data/run_phase_01_pipeline.py | Reproducible EDA execution | eda_summary.json | COMPLETED |
| REQ-P01-S06-010 | P01-S06 | src/data/eda.py | Deterministic grid sampling | phase_01_annotation_grid.png | COMPLETED |
| REQ-P01-S06-011 | P01-S06 | reports/eda_summary.json | Compatible stats policy check | eda_summary.json | COMPLETED |

### Phase 02 Requirements

Status values in this section are `PASS`, `PARTIAL`, `BLOCKED`, or `NOT VERIFIABLE`.
`PASS` means the code-level requirement has executable evidence; it does not
claim that a real-data experiment occurred.

| Requirement ID | Spec ID | Implementation | Test / Validation | Evidence | Status |
|---|---|---|---|---|---|
| REQ-P02-S01-001 | P02-S01 | `reports/experiments/phase_02_baseline_decision_record.md` | Decision review | Decision record | PASS |
| REQ-P02-S01-002 | P02-S01 | Decision record candidate table | Document review | Decision record | PASS |
| REQ-P02-S01-003 | P02-S01 | Decision rationale | Document review | Decision record | PASS |
| REQ-P02-S01-004 | P02-S01 | `src/segmentation/model.py` | Architecture review | Lightweight U-Net | PASS |
| REQ-P02-S01-005 | P02-S01 | Explicit Kaiming-normal (fan_out, ReLU) conv init; BatchNorm weight=1, bias=0 | Model unit tests | `src/segmentation/model.py` and real config | PASS |
| REQ-P02-S01-006 | P02-S01 | Phase 01 mask/task evidence | Manifest review | `data/external/dataset_registry.json` | PARTIAL |
| REQ-P02-S01-007 | P02-S01 | Test-independent selection record | Decision review | Decision record | PASS |
| REQ-P02-S02-001 | P02-S02 | `src/segmentation/dataset.py` | Manifest loader tests | Real FUSeg2021 manifest gate | PASS |
| REQ-P02-S02-002 | P02-S02 | Dataset image/mask loader | Dataset alignment tests | `tests/unit/test_phase_02_baseline.py` | PASS |
| REQ-P02-S02-003 | P02-S02 | Explicit preprocessing helpers | Preprocessing tests | Dataset docstrings/tests | PASS |
| REQ-P02-S02-004 | P02-S02 | Synchronized train flip | Flip alignment test | Dataset implementation | PASS |
| REQ-P02-S02-005 | P02-S02 | Deterministic val/test datasets | Determinism test | Dataset implementation | PASS |
| REQ-P02-S02-006 | P02-S02 | Tensor shape contracts | Shape tests | Dataset tests/report | PASS |
| REQ-P02-S02-007 | P02-S02 | Nearest-neighbor mask path | Mask tests | Dataset tests | PASS |
| REQ-P02-S02-008 | P02-S02 | VALID status filtering and path checks | Invalid/missing sample tests | Dataset implementation | PASS |
| REQ-P02-S02-009 | P02-S02 | Manifest split preservation | Split tests | Dataset implementation | PASS |
| REQ-P02-S02-010 | P02-S02 | Training batch sanity assertion | Real-data sanity-only run | FUSeg2021 sanity report | PASS |
| REQ-P02-S03-001 | P02-S03 | `LightweightUNet` | Forward-pass tests | `src/segmentation/model.py` | PASS |
| REQ-P02-S03-002 | P02-S03 | Explicit encoder/decoder/head | Architecture review | Model source | PASS |
| REQ-P02-S03-003 | P02-S03 | Raw-logit output/loss contract | Shape/range/loss tests | Model source/tests | PASS |
| REQ-P02-S03-004 | P02-S03 | `BCEDiceLoss` | Loss tests | Model source/tests | PASS |
| REQ-P02-S03-005 | P02-S03 | Parameter counter | Parameter test | 838,785 real-config parameters | PASS |
| REQ-P02-S03-006 | P02-S03 | Forward-pass verifier | Forward-pass test | Test suite | PASS |
| REQ-P02-S03-007 | P02-S03 | Device selection | CPU model tests | Trainer source | PASS |
| REQ-P02-S03-008 | P02-S03 | Plain PyTorch blocks | Source review | Model source | PASS |
| REQ-P02-S04-001 | P02-S04 | Real training config | JSON/config review | `configs/training/baseline_segmentation_real.json` | PASS |
| REQ-P02-S04-002 | P02-S04 | Seed setup | Trainer/source review | Trainer source | PASS |
| REQ-P02-S04-003 | P02-S04 | Adam configuration | Config review | Real config | PASS |
| REQ-P02-S04-004 | P02-S04 | Real manifest gate before training | Gate test and sanity-only run | `validate_manifest_for_training` | PASS |
| REQ-P02-S04-005 | P02-S04 | Checkpoint save/load | Checkpoint code review | Trainer source | PASS |
| REQ-P02-S04-006 | P02-S04 | Validation Dice selection | Trainer code review | Trainer source/config | PASS |
| REQ-P02-S04-007 | P02-S04 | Per-epoch log structure | Training code review | Trainer source | PASS |
| REQ-P02-S04-008 | P02-S04 | Explicit data/loss/write errors | Source review | Dataset/trainer source | PASS |
| REQ-P02-S04-009 | P02-S04 | Latest-checkpoint resume with RNG state | Checkpoint round-trip test | Trainer source/tests | PASS |
| REQ-P02-S04-010 | P02-S04 | Single-run config | Config review | Real config | PASS |
| REQ-P02-S05-001 | P02-S05 | Test evaluator | Real-data execution | No real test set | BLOCKED |
| REQ-P02-S05-002 | P02-S05 | Checkpoint loader | Code review | Evaluator/trainer source | PARTIAL |
| REQ-P02-S05-003 | P02-S05 | Dice/IoU/precision/recall | Controlled metric tests | Metrics source/tests | PASS |
| REQ-P02-S05-004 | P02-S05 | Mathematical definitions/edge rules | Metric tests | Metrics source | PASS |
| REQ-P02-S05-005 | P02-S05 | Per-sample JSON writer | Code review | Evaluator source | PARTIAL |
| REQ-P02-S05-006 | P02-S05 | Macro aggregation | Aggregation tests | Metrics source/tests | PASS |
| REQ-P02-S05-007 | P02-S05 | Imbalance rationale | Documentation review | Metrics/report | PASS |
| REQ-P02-S05-008 | P02-S05 | Actual-run-only policy | Gate/report review | Real report | BLOCKED |
| REQ-P02-S05-009 | P02-S05 | Reproducible evaluator command | Code/config review | Evaluation script | PARTIAL |
| REQ-P02-S05-010 | P02-S05 | Visualization hook | Code review | Evaluator source | PARTIAL |
| REQ-P02-S06-001 | P02-S06 | Rank-based selector | Code review | Evaluator source | PARTIAL |
| REQ-P02-S06-002 | P02-S06 | Seven-panel figure generator | Code review | Evaluator source | PASS |
| REQ-P02-S06-003 | P02-S06 | Observed failure collector | Code review | Evaluator source | PARTIAL |
| REQ-P02-S06-004 | P02-S06 | Evidence-based report section | Report review | Final report | BLOCKED |
| REQ-P02-S06-005 | P02-S06 | Medical boundary language | Report review | Final report | PASS |
| REQ-P02-S06-006 | P02-S06 | Limitations section | Report review | Final report | PASS |
| REQ-P02-S06-007 | P02-S06 | Later hypotheses without implementation | Report review | Final report | PASS |
| REQ-P02-S07-001 | P02-S07 | Experiment ID/config | Record review | `reports/experiments/spec-02-03/kaggle/spec-02-03/experiment_record.json` (real run). The `P02-baseline-unet-bce-dice-v1_*` record is the historical synthetic run. | PASS |
| REQ-P02-S07-002 | P02-S07 | Full real-data config | JSON review | Real config | PASS |
| REQ-P02-S07-003 | P02-S07 | Dataset/manifest provenance | Record/report review | FUSeg2021 config/manifest/report | PASS |
| REQ-P02-S07-004 | P02-S07 | Checkpoint provenance fields | Record/trainer review | Trainer source/config | PASS |
| REQ-P02-S07-005 | P02-S07 | Metric-to-output links | Report/evaluator review | reports/experiments/spec_02_03_report.md links every metric to its JSON output | PASS |
| REQ-P02-S07-006 | P02-S07 | Commands documented | Report review | Final report | PASS |
| REQ-P02-S07-007 | P02-S07 | Required report sections | Report review | Final report | PASS |
| REQ-P02-S07-008 | P02-S07 | No unsupported real claims | Audit review | Final report | PASS |
| REQ-P02-S07-009 | P02-S07 | Reconciled traceability matrix | Matrix review | This matrix | PASS |
| REQ-P02-S07-010 | P02-S07 | Accurate phase tracker | Tracker review | `MASTER_TRACKER.md` | PASS |
| REQ-P02-S07-011 | P02-S07 | Phase boundary preserved | Repository audit | Phase 03 started only after Phase 02 closed (2026-10-22) | PASS |

### Phase 02 Gate Summary

The SPEC-02-01 engineering gate is **PASS** for the verified FUSeg2021 data
contract, loader/model/loss implementation, sanity evidence, reproducibility
controls, and Kaggle-ready entrypoint. Multi-epoch GPU training is intentionally
deferred. SPEC-02-02 owns any later authorized labeled-test evaluation and error
review; the unlabeled public FUSeg2021 test images are not a result set.

**Reconciliation note (2026-10-21).** Rows marked PASS for P02-S04..S07 mean
the *mechanism* exists and is tested. They do not mean the spec is complete.
In `MASTER_TRACKER.md`:

- P02-S04 to P02-S07 are marked `DEFERRED → SPEC-02-02`.
- They become `COMPLETED` only when SPEC-02-02 delivers the real run, the
  held-out evaluation and the final record.

The evaluation-split decision is implemented (SPEC-02-03): internal val is
carved from train, with near-duplicate grouping, and the official val is the
held-out test set. REQ-P02-S05-001 becomes COMPLETED once the Kaggle
evaluation produces `heldout_test_evaluation.json`.

**Closure (2026-10-22).** SPEC-02-02 and SPEC-02-03 are COMPLETED. The Kaggle
run produced `heldout_test_evaluation.json`, and every metric was re-computed
independently on CPU (`reports/experiments/spec_02_03_report.md` §6).
P02-S04 to P02-S07 are now COMPLETED via SPEC-02-02/03.

## SPEC-02-03 Traceability

| Requirement | Implementation | Verification | Status |
|---|---|---|---|
| REQ-SPEC-02-03-001 held-out split | `src/data/heldout_split.py`, `scripts/data/build_fuseg2021_heldout_manifest.py` | `test_derive_heldout_manifest_*`, split report | PASS |
| REQ-SPEC-02-03-002 near-duplicate grouping | `src/data/near_duplicates.py` | `test_phash_*`, `test_near_duplicate_groups_are_transitive` | PASS |
| REQ-SPEC-02-03-003 test-neighbour quarantine | `derive_heldout_manifest` | `test_derive_heldout_manifest_roles_and_guards` | PASS (7 quarantined) |
| REQ-SPEC-02-03-004 selection isolation | `strong_trainer.py`, `config_strong.py`, `scripts/training/run_spec_02_03.py` | `test_strong_config_rejects_unsafe_values`, train smoke test | PASS |
| REQ-SPEC-02-03-005 native-resolution scoring | `src/segmentation/inference.py` | `test_tune_postprocessing_prefers_cleanup_and_scores`, CLI smoke run | PASS |
| REQ-SPEC-02-03-006 metrics | `src/segmentation/metrics.py` | `test_pooled_and_nonempty_metrics`, `test_hd95_edge_cases` | PASS |
| REQ-SPEC-02-03-007 external check | `scripts/data/build_lowerlimb_external_manifest.py`, `run_spec_02_03.py --external` | CLI smoke run | PASS |
| REQ-SPEC-02-03-008 reproducibility record | `run_spec_02_03.py` experiment record | CLI smoke run | PASS |
| Real held-out and external results | Kaggle T4 run, CPU re-verification | `reports/experiments/spec-02-03/*.json` | PASS |

## Revised Future Roadmap Traceability

The future work has been consolidated into `specs/REVISED_ROADMAP.md`:

| Consolidated phase | Specifications | Current traceability state |
|---|---|---|
| Phase 02 engineering | SPEC-02-01 | COMPLETED — `specs/phase-02/SPEC-02-01-baseline-engineering.md` |
| Phase 02 completion | SPEC-02-02, SPEC-02-03 | COMPLETED 2026-10-22; metrics independently re-computed on CPU |
| Phase 03 CV core | P03-S01–P03-S03 | COMPLETED — matrix below |
| Phase 04 longitudinal workflow | P04-S01–P04-S03 | COMPLETED — matrix below |
| Phase 05 product integration | P05-S01–P05-S03 | COMPLETED — matrix below |
| Phase 06 validation and release | P06-S01–P06-S03 | COMPLETED — matrix below (one PARTIAL item) |

## Phases 03–06 Requirement Matrix

Test files: S01i = `tests/integration/test_p03_s01_inference.py`, PIPE = `tests/integration/test_p03_pipeline.py`,
QG = `tests/quality/test_p03_s02_quality_gate.py`, MS = `tests/measurement/test_p03_s03_measurement.py`,
LG = `tests/longitudinal/test_p04_longitudinal.py`, API = `tests/api/test_p05_api.py`,
ST = `tests/api/test_p05_storage.py`, REL = `tests/release/test_p06_release.py`.

| Requirement | Implementation | Verification | Status |
|---|---|---|---|
| REQ-P03-S01-001 training preprocessing reused | `src/inference/engine.py` | S01i `test_shipped_config_reads_preprocessing_from_training_config`, `test_engine_matches_training_evaluation_path`; P06 cross-check against Phase 02 per-sample Dice | PASS |
| REQ-P03-S01-002 provenance in output | `engine.py` provenance | S01i `test_result_shapes_values_and_provenance`, `test_threshold_override_is_recorded` | PASS |
| REQ-P03-S01-003 typed input/artifact errors | `src/inference/errors.py` | S01i `test_input_errors_are_typed`, `test_checkpoint_errors_are_typed`, `test_malformed_config_is_rejected` | PASS |
| REQ-P03-S01-004 repeatable inference | `engine.py` (deterministic CPU) | S01i `test_repeated_inference_is_bit_identical`; P06 benchmark repeatability | PASS |
| REQ-P03-S02-001 status + reason codes | `src/quality/gate.py` | QG `test_each_reason_code_is_produced`, `test_multiple_reasons_are_all_reported` | PASS |
| REQ-P03-S02-002 config-driven, recorded thresholds | `configs/quality/` | QG `test_stricter_config_changes_the_decision`, `test_invalid_configs_are_refused`; `reports/quality/quality_gate_calibration.json` | PASS |
| REQ-P03-S02-003 rejects bypass inference | `src/inference/pipeline.py` | PIPE `test_rejected_image_never_reaches_the_model` | PASS |
| REQ-P03-S02-004 quality distinct from model failure | pipeline status; API 422 vs 500 | API `test_quality_rejection_is_distinct_and_stored`, `test_model_failure_is_stored_as_failed` | PASS |
| REQ-P03-S03-001 deterministic geometry | `src/measurement/engine.py` | MS `test_square_geometry_is_exact`, `test_disc_perimeter_and_shape_within_documented_tolerance`, `test_measurement_is_deterministic` | PASS |
| REQ-P03-S03-002 PIXEL_BASED / CALIBRATED | measurement basis | MS `test_calibrated_measurements_convert_lengths_and_areas`; API `test_uncalibrated_analysis_is_pixel_based` | PASS |
| REQ-P03-S03-003 physical units only with valid scale | calibration validation | MS `test_invalid_calibration_is_refused` | PASS |
| REQ-P03-S03-004 empty/disconnected/low-confidence | warnings, components | MS `test_empty_mask_is_explicit_not_zero_geometry`, `test_multiple_components_are_listed_largest_first`, `test_border_small_and_low_confidence_warnings`, `test_malformed_masks_raise` | PASS |
| REQ-P03-S03-005 provenance preserved | result serialisation | MS `test_result_serialises_and_round_trips_with_provenance` | PASS |
| REQ-P04-S01-001 case, examination, image distinct | `src/longitudinal/records.py` | LG `test_case_examination_image_are_distinct_records` | PASS |
| REQ-P04-S01-002 unknown identifiers stay unknown | records | LG `test_unknown_identifiers_stay_unknown_and_filenames_are_not_parsed` | PASS |
| REQ-P04-S01-003 provenance preserved | records | LG `test_completed_analysis_requires_full_provenance`, `test_pipeline_outcome_maps_to_records_with_provenance` | PASS |
| REQ-P04-S01-004 structured validation errors | `RecordValidationError` | LG `test_invalid_records_raise_structured_errors`; API `test_case_crud_and_validation` | PASS |
| REQ-P04-S02-001 explicit compatibility policy | `src/longitudinal/comparison.py` | LG `test_policy_is_mandatory`, `test_incompatible_pairs_are_unavailable` | PASS |
| REQ-P04-S02-002 missing info gives UNAVAILABLE | comparison reason codes | LG `test_unknown_case_on_examination_is_unavailable`, `test_calibrated_pair_uses_mm_and_warns_on_scale_change`; API `test_compare_unlinked_analyses_is_unavailable` | PASS |
| REQ-P04-S02-003 source references preserved | comparison output | LG `test_valid_pair_gives_deterministic_changes` | PASS |
| REQ-P04-S02-004 no cross-dataset patient links | identity policy | LG `test_unknown_identity_and_cross_dataset_are_never_linked` | PASS |
| REQ-P04-S03-001 trends from stored compatible results | `src/longitudinal/trends.py` | LG `test_known_series_gives_expected_trend`, `test_mixed_cases_are_refused`; API `test_trend_and_compare_end_to_end` | PASS |
| REQ-P04-S03-002 zero-denominator / missing data | trend exclusions | LG `test_zero_baseline_trend`, `test_zero_baseline_has_no_percentage`, `test_missing_and_incompatible_points_are_excluded_with_reasons`, `test_no_baseline_or_single_point_is_unavailable` | PASS |
| REQ-P04-S03-003 technical-only wording | `TREND_LABEL`, `TECHNICAL_LABEL` | REL `test_no_unqualified_clinical_claims` | PASS |
| REQ-P04-S03-004 reproducible trend artifacts | trends | LG `test_trend_is_reproducible` | PASS |
| REQ-P05-S01-001 versioned typed schemas | `src/api/schemas.py`, `/api/v1` | API `test_openapi_documents_versioned_routes`, `test_completed_analysis_contract` | PASS |
| REQ-P05-S01-002 distinct failure categories | `src/api/app.py` error envelope | API `test_every_error_has_a_failure_class`, `test_invalid_images_are_input_errors`, `test_storage_failure_is_infrastructure_error`, `test_readiness_reports_missing_model` | PASS |
| REQ-P05-S01-003 provenance in results | `AnalysisResponse` | API `test_completed_analysis_contract`, `test_model_info_exposes_versions_and_limitations` | PASS |
| REQ-P05-S01-004 testable without live dependencies | injectable engine, tiny random model | whole API suite runs in-process | PASS |
| REQ-P05-S02-001 distinct stored entities | `src/storage/database.py` | ST `test_round_trip_of_all_record_types`, `test_foreign_keys_are_enforced` | PASS |
| REQ-P05-S02-002 traceable to input and config | stored analysis, content-addressed blobs | ST `test_blob_store_is_content_addressed_and_blocks_traversal`, `test_mismatched_image_and_analysis_rejected`, `test_model_version_conflict` | PASS |
| REQ-P05-S02-003 transactional invalid writes | `save_analysis` transaction | ST `test_failed_write_rolls_back_whole_analysis`, `test_database_constraints_exist_at_sql_level`, `test_duplicate_case_is_a_conflict` | PASS |
| REQ-P05-S02-004 reproducible migrations/setup | schema migrations | ST `test_migrations_are_idempotent`; API `test_records_survive_restart`; smoke test on an empty data dir | PASS |
| REQ-P05-S03-001 dashboard uses API only | `src/dashboard/index.html` | API `test_dashboard_is_served_and_only_uses_the_api` | PASS |
| REQ-P05-S03-002 failures shown distinctly | dashboard error boxes | browser check against the real model; API failure-class tests | PASS (manual UI check) |
| REQ-P05-S03-003 units/calibration status shown | dashboard measurement table | browser check (5 px/mm uploads) | PASS (manual UI check) |
| REQ-P05-S03-004 honest missing longitudinal data | dashboard trend table with UNAVAILABLE reasons | API `test_unverified_case_trend_is_unavailable`; browser check | PASS |
| REQ-P06-S01-001 per-component metrics | `scripts/evaluation/run_phase_06_validation.py` | `reports/final/p06_validation_*.json` | PASS |
| REQ-P06-S01-002 split/dataset/artifact provenance | validation report provenance | manifest checksum verified before the run | PASS |
| REQ-P06-S01-003 observed errors vs hypotheses | `reports/final/phase_06_validation_report.md` | report review | PASS |
| REQ-P06-S01-004 distributions, not one score | histograms, quantiles, size terciles | `reports/figures/p06/*.png` | PASS |
| REQ-P06-S02-001 repeatability | benchmark repeatability block | `reports/final/p06_benchmark.json` | PASS |
| REQ-P06-S02-002 latency/memory with hardware | `scripts/evaluation/run_phase_06_benchmark.py` | `reports/final/p06_benchmark.json` | PASS |
| REQ-P06-S02-003 five failure classes | `failure_class` in the error envelope | API `test_every_error_has_a_failure_class`; benchmark boundary inputs | PASS |
| REQ-P06-S02-004 optimisation needs a measured bottleneck | benchmark `optimisation_decision` | none applied (no latency requirement) | PASS |
| REQ-P06-S03-001 clean install and start | `docs/release/RELEASE.md`, `.github/workflows/ci.yml` | smoke test on an empty data dir; empty Python 3.12 venv on Windows gave 263 passed, 2 skipped; Linux waits for the first Actions run | PARTIAL |
| REQ-P06-S03-002 health: service vs model | `/health/live`, `/health/ready` | REL `test_health_separates_service_from_model`; API `test_readiness_reports_missing_model` | PASS |
| REQ-P06-S03-003 versions/configs/limitations/commands | `scripts/deployment/build_release_manifest.py` | REL `test_release_manifest_builds`; `reports/final/release_manifest.json` | PASS |
| REQ-P06-S03-004 no clinical implication | limitations, labels, dashboard, RELEASE.md | REL `test_no_unqualified_clinical_claims` | PASS |

## Phases 07–10 (planned)

These requirements are specified and not implemented. The paths are planned locations.

| Requirement | Planned implementation | Planned test | Planned evidence | Status |
|---|---|---|---|---|
| REQ-P07-S01-001 | `.github/workflows/ci.yml` | Workflow run on a pull request | Workflow written; ruff, mypy and pytest pass locally; no Actions run yet | IN_PROGRESS |
| REQ-P07-S01-002 | `.github/workflows/ci.yml` install job | Matrix job | Windows, Python 3.12, empty venv: 263 passed, 2 skipped on 2026-10-30; Linux needs the Actions run | IN_PROGRESS |
| REQ-P07-S01-003 | `.github/workflows/ci.yml` docker job | Container start check | Written; Docker is not installed locally, so the image build is unproven | IN_PROGRESS |
| REQ-P07-S01-004 | Published Space | `smoke_test.py --url <space>` | Waiting for `hf auth login` and approval to publish | BLOCKED |
| REQ-P07-S01-005 | `scripts/deployment/fetch_checkpoint.py`, `scripts/deployment/check_refuses_bad_model.py` | Container test with a wrong hash | Running service with a tampered checkpoint gave 503 on readiness and analysis, CHECKPOINT_CHECKSUM_MISMATCH; container run needs the docker job | IN_PROGRESS |
| REQ-P07-S02-001 | `src/storage/repository.py` | `tests/storage/test_repository.py` | `test_api_layer_contains_no_sql`, 279 passed on PostgreSQL | COMPLETED |
| REQ-P07-S02-002 | `src/storage/migrations/` | `test_migration_round_trip`, `test_migrations_match_the_models` | Round trip passes on SQLite and PostgreSQL 16 | COMPLETED |
| REQ-P07-S02-003 | Parametrised test fixture | `DFU_TEST_DATABASE_URL`; CI `postgres` job | Local PostgreSQL 16: all passed. CI awaits a push | IN_PROGRESS |
| REQ-P07-S02-004 | `scripts/deployment/import_sqlite.py` | `test_import_verifies_counts` | `reports/deployment/p07_s02_import_report.json` | COMPLETED |
| REQ-P07-S02-005 | `src/api/app.py` | `tests/api/`, `tests/storage/test_database_outage.py` | Smoke test 8/8 with the real model on PostgreSQL | COMPLETED |
| REQ-P07-S03-001 | `src/storage/blobs.py` | `tests/storage/test_blob_contract.py` | Contract tests pass on local disk and moto. MinIO in CI awaits a push | IN_PROGRESS |
| REQ-P07-S03-002 | `src/storage/blobs.py` | `test_corrupt_blob_detected` | Test run | COMPLETED |
| REQ-P07-S03-003 | `src/api/uploads.py` | `test_upload_url_limits` | Test run | COMPLETED |
| REQ-P07-S03-004 | `src/api/uploads.py` | `test_rejects_disguised_file` | Test run | COMPLETED |
| REQ-P07-S03-005 | `src/storage/blobs.py` | `test_no_public_access` | Test run on moto. A hosted bucket has not been created or reviewed | IN_PROGRESS |
| REQ-P07-S04-001 | `src/api/auth.py` | `tests/api/test_auth.py` | Test run | COMPLETED |
| REQ-P07-S04-002 | Repository owner filter | `test_cross_user_isolation`, for every route | Test run | COMPLETED |
| REQ-P07-S04-003 | `src/api/auth.py` | `test_rejects_bad_tokens` | `reports/deployment/p07_s04_security_review.md` | COMPLETED |
| REQ-P07-S04-004 | `src/api/account.py` | `test_account_deletion_is_complete` | Test run | COMPLETED |
| REQ-P07-S04-005 | Alembic revision | `test_owner_migration` | Passes locally on SQLite and PostgreSQL 16. CI log awaits a push | IN_PROGRESS |
| REQ-P07-S05-001 | `src/api/analyses_v2.py` | `test_submit_does_not_run_model` | Test run, with the queue stubbed. Real Redis submits are covered by `tests/worker/test_redis.py` | COMPLETED |
| REQ-P07-S05-002 | `src/worker/state.py` | `test_state_machine`, `test_a_job_only_moves_from_the_state_it_is_in` | Test run | COMPLETED |
| REQ-P07-S05-003 | `src/worker/tasks.py` | `test_redelivery_is_idempotent`, `test_only_one_worker_can_claim_a_job`, `test_two_workers_finish_a_burst_with_no_duplicates_or_losses` | Test run | COMPLETED |
| REQ-P07-S05-004 | `src/worker/tasks.py` | `test_retry_policy`, `test_input_and_model_errors_do_not_retry`, `test_a_retry_is_delivered_after_its_back_off` | Test run | COMPLETED |
| REQ-P07-S05-005 | `src/worker/tasks.py` | `test_worker_matches_pipeline` | `reports/deployment/p07_s05_parity_report.json`: 5 real images, identical results and mask hashes | COMPLETED |
| REQ-P07-S05-006 | `src/api/app.py` | `test_readiness_covers_the_queue`, `test_model_route_works_without_a_model_in_the_api` | Test run | COMPLETED |
| REQ-P07-S06-001 | `scripts/deployment/export_onnx.py` | `test_export_records_provenance` | `models/metadata/` record | NOT_STARTED |
| REQ-P07-S06-002 | `src/inference/onnx_engine.py` | `test_engine_interface_parity` | Test run | NOT_STARTED |
| REQ-P07-S06-003 | `scripts/evaluation/run_onnx_parity.py` | Parity run | `reports/final/p07_s06_onnx_parity.json` | NOT_STARTED |
| REQ-P07-S06-004 | `scripts/evaluation/run_phase_06_benchmark.py` | Benchmark run | `reports/final/p07_s06_onnx_benchmark.json` | NOT_STARTED |
| REQ-P07-S06-005 | `configs/inference/` | Decision entry | `docs/architecture/decisions.md` | NOT_STARTED |
| REQ-P08-S01-001 | `web/lib/api/` | CI schema diff | CI log | NOT_STARTED |
| REQ-P08-S01-002 | `web/components/MedicalNotice.tsx` | Playwright check over all routes | Test report | NOT_STARTED |
| REQ-P08-S01-003 | `web/middleware.ts` | Playwright auth test | Test report | NOT_STARTED |
| REQ-P08-S01-004 | `web/lib/errors.ts` | Unit test over all categories | Test report | NOT_STARTED |
| REQ-P08-S01-005 | `web/` layouts | axe and Playwright | Test report | NOT_STARTED |
| REQ-P08-S02-001 | `web/components/Upload.tsx` | Playwright upload test | Test report | NOT_STARTED |
| REQ-P08-S02-002 | `web/app/analyses/[id]/` | Playwright with mocked states | Test report | NOT_STARTED |
| REQ-P08-S02-003 | `web/components/QualityResult.tsx` | Component test | Test report | NOT_STARTED |
| REQ-P08-S02-004 | `web/components/Measurements.tsx` | Component test | Test report | NOT_STARTED |
| REQ-P08-S02-005 | `web/components/Provenance.tsx` | Playwright check | Test report | NOT_STARTED |
| REQ-P08-S02-006 | `web/e2e/` | Playwright in CI | Test report | NOT_STARTED |
| REQ-P08-S03-001 | `web/components/TrendChart.tsx` | Component test | Test report | NOT_STARTED |
| REQ-P08-S03-002 | `web/components/Exclusions.tsx` | Component test | Test report | NOT_STARTED |
| REQ-P08-S03-003 | `web/components/TrendChart.tsx` | Component test | Test report | NOT_STARTED |
| REQ-P08-S03-004 | `web/components/TrendNotice.tsx` | Playwright check | Test report | NOT_STARTED |
| REQ-P08-S03-005 | `web/components/Compare.tsx` | Component test | Test report | NOT_STARTED |
| REQ-P09-S01-001 | `src/measurement/marker.py` | `tests/measurement/test_marker.py` | Test run | NOT_STARTED |
| REQ-P09-S01-002 | `src/measurement/marker.py` | `test_marker_fallbacks` | Test run | NOT_STARTED |
| REQ-P09-S01-003 | `scripts/evaluation/run_marker_validation.py` | Validation run | `reports/final/p09_s01_marker_validation.json` | NOT_STARTED |
| REQ-P09-S01-004 | `src/measurement/calibration.py` | `test_scale_conflict` | Test run | NOT_STARTED |
| REQ-P09-S01-005 | API limitation text | `test_limitation_present` | Test run | NOT_STARTED |
| REQ-P09-S02-001 | `web/components/Heatmap.tsx` | Component test | Test report | NOT_STARTED |
| REQ-P09-S02-002 | `src/inference/uncertainty.py` | `test_disagreement_known_inputs` | Test run | NOT_STARTED |
| REQ-P09-S02-003 | `scripts/evaluation/run_uncertainty_study.py` | Study run | `reports/final/p09_s02_uncertainty.json` | NOT_STARTED |
| REQ-P09-S02-004 | `web/components/Heatmap.tsx` | Language test | Test report | NOT_STARTED |
| REQ-P09-S03-001 | `web/components/MaskEditor/` | Playwright test | Test report | NOT_STARTED |
| REQ-P09-S03-002 | `src/api/corrections.py` | `test_original_is_immutable` | Test run | NOT_STARTED |
| REQ-P09-S03-003 | `src/api/corrections.py` | `test_measurements_from_corrected_mask` | Test run | NOT_STARTED |
| REQ-P09-S03-004 | `src/longitudinal/` | `test_trend_marks_corrected` | Test run | NOT_STARTED |
| REQ-P09-S03-005 | `src/api/corrections.py` | `test_export_requires_opt_in` | Test run | NOT_STARTED |
| REQ-P09-S04-001 | `reports/experiments/p09_s04_protocol.md` | Review of the protocol | Study report | NOT_STARTED |
| REQ-P09-S04-002 | `data/manifests/` | Split leakage test | Manifest | NOT_STARTED |
| REQ-P09-S04-003 | `scripts/evaluation/` | Evaluation run | Comparison report | NOT_STARTED |
| REQ-P09-S04-004 | `docs/deployment/MODEL_CARD.md` | Claim-check test | Model card | NOT_STARTED |
| REQ-P09-S04-005 | `configs/inference/` | Hash test | Release record | NOT_STARTED |
| REQ-P10-S01-001 | `src/api/middleware.py` | `test_request_id_propagates` | Test run | NOT_STARTED |
| REQ-P10-S01-002 | `src/observability/metrics.py` | `test_metrics_exposed` | Dashboard export | NOT_STARTED |
| REQ-P10-S01-003 | `src/observability/scrub.py` | `test_log_scrubbing` | Test run | NOT_STARTED |
| REQ-P10-S01-004 | `deploy/monitoring/alerts.yml` | Injected-fault test | Alert record | NOT_STARTED |
| REQ-P10-S02-001 | `tests/load/locustfile.py` | Load run | `reports/final/p10_s02_load.json` | NOT_STARTED |
| REQ-P10-S02-002 | `scripts/evaluation/` | Load run | `reports/final/p10_s02_load.json` | NOT_STARTED |
| REQ-P10-S02-003 | `docs/deployment/SLO.md` | Document review | SLO document | NOT_STARTED |
| REQ-P10-S02-004 | `src/api/analyses_v2.py` | Overload run | Report | NOT_STARTED |
| REQ-P10-S02-005 | `deploy/` | Scaling run | Report | NOT_STARTED |
| REQ-P10-S03-001 | `src/worker/retention.py` | `test_retention_deletes_all` | Retention log | NOT_STARTED |
| REQ-P10-S03-002 | `src/preprocessing/sanitise.py` | `test_exif_removed` | Test run | NOT_STARTED |
| REQ-P10-S03-003 | `src/api/consent.py` | `test_upload_requires_consent` | Test run | NOT_STARTED |
| REQ-P10-S03-004 | `src/api/limits.py` | `test_rate_limits` | Test run | NOT_STARTED |
| REQ-P10-S03-005 | `docs/deployment/THREAT_MODEL.md` | Document review | Threat model | NOT_STARTED |
| REQ-P10-S03-006 | `.github/workflows/ci.yml` | CI job | Scan report | NOT_STARTED |
| REQ-P10-S04-001 | `src/mlops/registry.py` | `test_registry_requires_fields` | Test run | NOT_STARTED |
| REQ-P10-S04-002 | `scripts/deployment/promote_model.py` | `test_gate_blocks_regression` | Promotion record | NOT_STARTED |
| REQ-P10-S04-003 | `scripts/deployment/promote_model.py` | Rollback drill | Drill record | NOT_STARTED |
| REQ-P10-S04-004 | `src/mlops/drift.py` | `test_drift_detects_shift` | Dashboard export | NOT_STARTED |
| REQ-P10-S04-005 | `src/mlops/drift.py` | Text review | Alert sample | NOT_STARTED |

No future requirement is considered implemented or complete merely because the
architecture document contains a conceptual module boundary.
