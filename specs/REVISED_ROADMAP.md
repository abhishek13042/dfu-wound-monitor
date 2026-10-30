# DFU-WoundMonitor — Revised Spec-Driven Roadmap

## 1. Purpose

This document replaces the over-sliced Phase 03–12 roadmap with a smaller set
of implementation phases. Phase 00 and Phase 01 remain completed historical
foundations. Phases 00–06 are complete. Phases 07–10 are specified and not started (section 12).

The roadmap is intentionally product-oriented: each phase delivers a usable
capability and has a small number of specifications with clear interfaces,
tests, evidence, and acceptance gates.

## 2. Spec-Driven Development Rule

No implementation begins for a future phase until its phase specification is
approved. Each specification must use `specs/SPEC_TEMPLATE.md` and contain:

1. objective, scope, and non-goals;
2. numbered requirements;
3. dependencies and interface contracts;
4. invariants and failure behavior;
5. implementation tasks;
6. automated tests and acceptance criteria;
7. reproducible evidence and limitations;
8. traceability from requirement to code, test, and evidence.

The phase gate is the only point at which a specification may become
`COMPLETED`.

## 3. Consolidated Phase Structure

| Phase | Name | Specs | Depends on | Gate |
|---|---|---|---|---|
| 00 | Project definition and system specification | P00-S01–P00-S07 | None | Completed foundation |
| 01 | Dataset and data engineering | P01-S01–P01-S06 | Phase 00 | Verified manifests and data contracts |
| 02 | Baseline segmentation completion | SPEC-02-01, SPEC-02-02 | Phase 01 | Real baseline, authorized evaluation, reproducibility record |
| 03 | Core CV inference and measurements | P03-S01–P03-S03 | Phase 02 | One validated image-to-measurement workflow |
| 04 | Longitudinal wound-monitoring workflow | P04-S01–P04-S03 | Phase 03 | Multi-examination comparison contract |
| 05 | Product integration | P05-S01–P05-S03 | Phases 03–04 | API, persistence, and minimal dashboard workflow |
| 06 | System validation and release | P06-S01–P06-S03 | Phase 05 | End-to-end evidence and reproducible release |

The former Phase 03–12 sequence is retired as an active execution plan. Its
goals are mapped into Phases 03–06 below. No separate phase is created for
every model type, subsystem, or technology.

## 4. Phase 02 — Baseline Segmentation Completion

### SPEC-02-01 — Baseline engineering implementation

Status: engineering PASS; GPU training intentionally deferred.

Scope already completed:

- verified FUSeg2021 manifest and official split contract;
- synchronized preprocessing and augmentation;
- lightweight U-Net and stable BCE-with-logits plus Dice loss;
- deterministic configuration, checkpointing, resume, and logging;
- bounded real-data sanity checks;
- Kaggle-ready entrypoint.

### SPEC-02-02 — Baseline run, authorized evaluation, and error review

This single specification absorbs the remaining granular P02-S04 through
P02-S07 work.

It SHALL cover:

- the real multi-epoch Kaggle GPU run;
- validation-Dice checkpoint selection;
- interrupted-run resume verification;
- evaluation only on an authorized labeled evaluation set;
- per-sample and aggregate metrics;
- representative qualitative review and evidence-based error categories;
- final experiment/reproducibility record;
- explicit handling of the unlabeled public FUSeg2021 test split.

It SHALL NOT claim a public-test result when labels are unavailable.

Gate evidence: best/latest checkpoints, complete training log, evaluation
artifact, qualitative review, reproducibility record, and updated traceability.

## 5. Phase 03 — Core CV Inference and Measurements

Phase 03 combines the model-serving path, input quality behavior, and
image-derived measurements. Detection/localization is not a mandatory phase by
itself: full-image segmentation remains the default unless evidence shows that
localization is required for the approved workflow.

### P03-S01 — Inference and model artifact contract

Defines the versioned inference input/output contract, preprocessing reuse,
checkpoint loading, thresholding, provenance, and structured inference errors.

Acceptance examples:

- one image produces a versioned segmentation result;
- model, config, preprocessing, and dataset references are preserved;
- malformed input and missing checkpoint failures are explicit;
- inference never silently changes preprocessing from training.

### P03-S02 — Image quality gate

Defines deterministic technical checks for unreadable images, resolution,
blur, illumination, glare, and field-of-view limitations. Quality rejection
must be distinguishable from model failure and must bypass downstream
inference.

Acceptance examples:

- accepted/rejected status has a reason code;
- thresholds are configuration-driven;
- controlled fixtures cover each failure mode;
- no clinical diagnosis or treatment conclusion is produced.

### P03-S03 — Wound measurement engine

Defines reproducible measurements from the segmentation mask: pixel area,
perimeter, bounding box, shape descriptors, and optional physical units only
when calibration is explicitly available.

Acceptance examples:

- known masks produce known geometric values;
- pixel-based and calibrated measurements are clearly distinguished;
- empty, disconnected, malformed, and low-confidence masks have explicit
  behavior;
- every measurement retains input, model, calibration, and configuration
  provenance.

Calibration note (audit 2026-10-21): none of the acquired datasets contain a
reliable physical scale, so the default output is **pixels**. Physical units
(mm², mm) are produced only from an explicit calibration source, either:

- a detected reference marker of known size (e.g. a printed ruler or a
  fiducial sticker) in the same plane as the wound; or
- a user-entered pixels-per-mm value.

The source is recorded with each measurement, and a missing or failed
calibration falls back to pixel units with a reason code. Marker detection,
if implemented, needs its own spec and fixtures. Perspective distortion and
foot curvature are documented limitations: area from a single 2D photo is an
estimate.

## 6. Phase 04 — Longitudinal Wound-Monitoring Workflow

Phase 04 creates the domain workflow without inventing patient identity or
clinical conclusions.

### P04-S01 — Examination and case data contract

Defines case, patient-reference, examination, image, inference, segmentation,
and measurement records. Unknown identifiers remain unknown; they are never
inferred from filenames.

### P04-S02 — Multi-examination alignment and comparison

Defines how two or more examinations are compared when valid identity,
timestamps, and compatible measurements exist. It covers missing visits,
different image quality, calibration changes, and incompatible model versions.

### P04-S03 — Trajectory and technical trend outputs

Defines area change, percentage change, boundary/measurement comparison, and
technical trend visualizations. Outputs must be described as image-derived
technical trends, not healing diagnoses or treatment recommendations.

Gate evidence: schema tests, synthetic multi-visit fixtures, missing-data tests,
and a reproducible example workflow.

Longitudinal data note (audit 2026-10-21): no acquired dataset provides
multi-visit series with reliable patient identity and timestamps. Phase 04 is
therefore validated on **synthetic, clearly labelled** sequences. These are
built either from controlled mask transformations (known area changes) or from
user-provided demo series. All Phase 04 outputs and reports must say that the
trend logic is verified on synthetic data and that no real-world longitudinal
accuracy is claimed. FUSeg images that look like the same wound must never be
treated as a time series, because their order and identity are unknown.

## 7. Phase 05 — Product Integration

Phase 05 combines backend, persistence, and dashboard work around the already
validated CV workflow.

### P05-S01 — Inference API contract

Defines upload/inference/status/result routes, request and response schemas,
structured errors, model-version reporting, and deterministic service tests.

### P05-S02 — Persistence and model-result storage

Defines storage for examination references, input images or paths, model
versions, inference outputs, measurements, provenance, and failure records.
The storage design must preserve the distinction between patient identity,
examination identity, and technical inference identity.

### P05-S03 — Minimal monitoring dashboard

Defines the smallest user workflow: submit or select an examination, display
quality status, show segmentation and measurements, and compare available
examinations. The dashboard consumes the API and never calls model code
directly.

Gate evidence: API contract tests, persistence migration/round-trip tests,
service integration test, and one demonstrable end-to-end UI workflow.

## 8. Phase 06 — System Validation and Release

Phase 06 replaces separate evaluation, error-analysis, deployment, and final
integration phases.

### P06-S01 — End-to-end validation and error analysis

Defines the final technical evaluation protocol across the approved workflow:
segmentation, quality gate, measurements, longitudinal comparison, API
behavior, and representative failure cases.

### P06-S02 — Reliability, reproducibility, and performance

Defines repeatability checks, latency/memory measurements, malformed-input
behavior, artifact/version verification, and bounded robustness experiments.
Optimization is performed only when a measured bottleneck justifies it.

### P06-S03 — Deployment and portfolio release

Defines the reproducible runtime package, configuration, migrations, startup
instructions, health checks, security boundary, demo data policy, limitations,
and final project report.

Gate evidence: end-to-end tests, performance report, deployment smoke test,
release checklist, limitations register, and traceability sign-off.

## 9. Deferred / Optional Work

The following are backlog items, not mandatory phases:

- segmentation architectures beyond the SPEC-02-03 pretrained ResNet U-Net
  (a pretrained encoder is now required; it is no longer optional);
- tissue classification/segmentation;
- additional external-dataset generalization;
- uncertainty estimation;
- detector/localizer implementation when full-image segmentation is adequate;
- optimization without a measured bottleneck (ONNX is now P07-S06, with a measurement gate);
- multi-tenant organisations and multi-region scaling (single-user accounts are P07-S04);
- clinical validation or treatment recommendation features.

Each optional item requires its own approved specification before implementation.

## 10. Dependency Graph

```text
SPEC-02-01
    ↓
SPEC-02-02 / SPEC-02-03 (held-out split + pretrained model)
    ↓
P03-S01 ─────┐
P03-S02 ─────┼──→ P04-S01 → P04-S02 → P04-S03 ──┐
P03-S03 ─────┘                                    │
                                                  ▼
                         P05-S01 → P05-S02 → P05-S03
                                                  ↓
                         P06-S01 → P06-S02 → P06-S03
```

P03-S02 and P03-S03 may be developed in parallel with P04-S01 after the
inference contract is stable. Product integration does not begin until the
core result contracts are stable.

## 11. Phase Gate Policy

A phase is complete only when:

- all owned specifications are completed;
- automated tests pass;
- evidence artifacts exist and are linked;
- reproducibility commands work from a clean environment;
- limitations and unsupported claims are recorded;
- the next phase has approved inputs.

This roadmap reduces the number of management phases without weakening
requirements, testing, or traceability.

## 12. Phases 07–10 — Production Platform

These phases turn the single-machine prototype into a public, multi-user research demonstration. It remains a
research prototype. All specifications are `NOT_STARTED`, and each needs approval before implementation.

| Spec | Name | Depends on |
|---|---|---|
| P07-S01 | Public Demo and Continuous Integration | P06-S03 |
| P07-S02 | PostgreSQL and Managed Migrations | P05-S02, P07-S01 |
| P07-S03 | Object Storage and Pre-Signed Uploads | P07-S02 |
| P07-S04 | Authentication and Data Ownership | P07-S02 |
| P07-S05 | Asynchronous Inference Queue and Workers | P07-S02, P07-S03 |
| P07-S06 | ONNX Export and Serving Parity | P03-S01, P07-S01 |
| P08-S01 | Next.js Frontend Foundation | P07-S04 |
| P08-S02 | Analysis and Case Workflows | P08-S01, P07-S03, P07-S05 |
| P08-S03 | Longitudinal Views | P08-S02, P04-S03 |
| P09-S01 | Reference-Marker Calibration | P03-S03, P08-S02 |
| P09-S02 | Model Confidence Visualisation | P03-S01, P08-S02 |
| P09-S03 | Mask Correction Editor | P08-S02, P03-S03, P07-S02 |
| P09-S04 | External Generalisation Study | SPEC-02-03, P06-S01 |
| P10-S01 | Observability | P07-S05 |
| P10-S02 | Load Testing and Service Objectives | P10-S01, P07-S06 |
| P10-S03 | Security and Privacy Controls | P07-S03, P07-S04, P08-S02 |
| P10-S04 | Model Lifecycle and Drift Monitoring | P07-S06, P09-S03, P10-S01 |

```text
P07-S01 → P07-S02 → P07-S03 ─┐
   │         ├──→ P07-S04 ───┼──→ P08-S01 → P08-S02 → P08-S03
   │         └───────────────┤                 │
   └──→ P07-S06              └──→ P07-S05 ─────┤
                                    │          ├──→ P09-S01, P09-S02, P09-S03
                                    ▼          ▼
                                 P10-S01 → P10-S02, P10-S03, P10-S04

P09-S04 (generalisation study) depends only on SPEC-02-03 and P06-S01, and can start at any time.
```

P07-S01 comes first, because it closes the last open release item and protects all later work with CI.
