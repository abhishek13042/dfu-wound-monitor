# DFU-WoundMonitor

**Computer Vision–Based Longitudinal Diabetic Foot Wound Monitoring System**

## Status

**Project Status:** Phases 00–06 COMPLETED (research prototype). The SPEC-02-03 pretrained ResNet34 U-Net scores held-out pooled Dice 0.922 / macro Dice 0.841 on 191 FUSeg2021 images (independently re-computed on CPU); see `reports/experiments/spec_02_03_report.md`.
**Implementation:** The system runs end to end:
- inference contract, image quality gate, and measurement engine (Phase 03);
- examination records, comparison, and technical trends (Phase 04);
- FastAPI service with SQLite + blob persistence and a dashboard (Phase 05);
- end-to-end validation, benchmark, and release tooling (Phase 06): see `reports/final/phase_06_validation_report.md` and `docs/release/RELEASE.md`.
**Datasets:** FUSeg2021 is the primary segmentation dataset for SPEC-02-01. Its public test images have no usable ground-truth masks.
- LowerLimbFeetWound V3 is prepared as an external, no-tuning evaluation set (SPEC-02-03). Medetec and DFUTissueSegNet are acquired but not yet used.
- DFUC2020, DFUC2021 and DFUC2022 are **blocked** pending the official license application.
- See `data/external/dataset_registry.json` and `reports/dataset_acquisition_report.md`.

**Historical data:** The earlier synthetic demonstration remains preserved and clearly separated from real-data evidence.
**Known gaps:**
- A fresh-machine install has not been exercised (REQ-P06-S03-001 is PARTIAL).
- There is no stated latency requirement, so no optimisation has been applied.
- Real longitudinal patient series are not available. Trends were exercised with constructed examination sequences only.

---

> **IMPORTANT MEDICAL NOTICE & DISCLAIMER**  
> **DFU-WoundMonitor** is a research and clinical decision-support engineering prototype designed for wound image analysis, quantitative measurement estimation, and longitudinal tracking.  
> - It is **NOT** a diagnostic system and does **NOT** provide medical diagnoses.  
> - It does **NOT** make treatment decisions or clinical recommendations.  
> - It is not intended to replace professional clinical judgment or direct patient assessment by licensed healthcare providers.

---

## Purpose

Diabetic Foot Ulcers (DFUs) present significant risks of morbidity, infection, and amputation. Longitudinal tracking and quantitative assessment of wound characteristics (e.g., area trajectory, boundary delineation, visual quality) are critical for monitoring healing progress.

DFU-WoundMonitor is being developed as a portfolio-grade Computer Vision and Deep Learning system to demonstrate rigorous engineering across:
- **Computer Vision & Deep Learning**: Semantic segmentation, image quality assessment, and optional wound localization.
- **Quantitative Measurement**: Area and boundary tracking over time.
- **Longitudinal Image Analysis**: Change detection and trajectory evaluation across examination visits.
- **Engineering Rigor**: Spec-driven development, modular architecture, robust testing, API design, database modeling, deployment, and error analysis.

### Current SPEC-02-01 Gate

The baseline task is binary wound segmentation on verified FUSeg2021 data using
a configurable lightweight four-level U-Net. The official train and validation
assignments are preserved; exact duplicate image collisions and one validation
mask with an unexpected value were quarantined without changing raw files.
Training uses only the leakage-checked annotated train split, while validation
selects the best checkpoint. The 200 public FUSeg test images have no released
ground-truth masks, so they are not evaluated as labeled data in SPEC-02-01.
The historical synthetic demonstration is preserved as
`P02-DEMO-SYNTHETIC-LEAKED` and its perfect metrics are not real-data evidence.

### SPEC-02-03 — Pretrained model and held-out evaluation

`specs/phase-02/SPEC-02-03-strong-segmentation.md` defines the main result:

- **Model.** An ImageNet-pretrained ResNet34 U-Net at the native 512 px,
  trained with strong augmentation, AdamW, warmup + cosine LR, AMP and EMA.
- **Split.** Official validation becomes the held-out test set (191 images).
  Internal validation (118 images) is carved from train with near-duplicate
  grouping. 7 train images that are near-duplicates of test images are
  quarantined.
- **Tuning.** The threshold and minimum component area are tuned on internal
  validation only. Test images are scored once, at native resolution, with
  flip TTA.
- **Metrics.** Macro, pooled, non-empty-subset and HD95.
- **External check.** LowerLimbFeetWound V3, evaluated without any tuning.

```bash
python scripts/run_spec_02_03.py --train --evaluate --external     --data-root "/kaggle/input/<fuseg>/Foot Ulcer Segmentation Challenge"     --external-data-root "/kaggle/input/<lowerlimb>/V3/extracted"     --output-root /kaggle/working/spec-02-03
```

## Run the system

```bash
python -m pip install -r requirements.txt
# place the checkpoint at models/checkpoints/spec-02-03/resnet34_unet_512_best.pth (SHA-256 in docs/release/RELEASE.md)
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000   # dashboard: http://127.0.0.1:8000/dashboard
python scripts/deployment/smoke_test.py
python -m pytest -q
```

Pipeline: upload → decode/validate → quality gate (reject with reason codes) →
segmentation → measurement (pixel, or mm when `pixels_per_mm` is given) →
stored record and artifacts → examination comparison and trends.

### Docker / Hugging Face Spaces demo

```bash
docker build -f docker/production/Dockerfile -t dfu-woundmonitor .
docker run --rm -p 7860:7860 -v "$PWD/models:/home/user/app/models" dfu-woundmonitor
python scripts/deployment/build_hf_space.py      # assembles dist/hf_space/ for a Docker Space
```

The checkpoint is fetched at container start from a Hugging Face model repo (`DFU_CHECKPOINT_REPO`)
and is used only if its SHA-256 matches the pinned value. Publishing steps: [docs/deployment/HUGGINGFACE.md](docs/deployment/HUGGINGFACE.md).

---

## Development Method: Spec-Driven Development (SDD)

This repository follows a strict Spec-Driven Development methodology. No implementation code, dataset ingestion, or model training proceeds without an approved specification, measurable requirements, and explicit acceptance criteria.

```
PROJECT
   ↓
 PHASE
   ↓
SPECIFICATION
   ↓
REQUIREMENTS
   ↓
 DESIGN
   ↓
IMPLEMENTATION TASKS
   ↓
  CODE
   ↓
 TESTS
   ↓
EVIDENCE
   ↓
ACCEPTANCE
   ↓
PHASE GATE
```

The `specs/` directory is the single source of truth for all requirements, designs, interfaces, and acceptance evidence.
The consolidated remaining implementation roadmap is maintained in
`specs/REVISED_ROADMAP.md`; the older Phase 03–12 breakdown is retained only
as historical planning context.

---

## Repository Structure

Folders marked `(placeholder)` contain only `.gitkeep` or README files and are
not used by the implemented system.

```
dfu-wound-monitor/
├── README.md             # Project overview, medical disclaimer, and workflow
├── LICENSE               # Project licensing terms
├── .gitignore            # Git exclusion rules (data, weights, artifacts)
├── pyproject.toml        # Build configuration and project metadata
├── requirements.txt      # Pinned runtime dependencies (torch lower-bounded)
├── requirements-dev.txt  # Optional lint/format/type tools
├── Makefile              # Development, linting, testing, and lifecycle shortcuts
│
├── specs/                # Source of truth: specifications, tracker, traceability
│   ├── MASTER_TRACKER.md      # Phase and specification progress tracking
│   ├── TRACEABILITY.md        # Requirement-to-evidence matrix
│   ├── REVISED_ROADMAP.md     # Consolidated remaining implementation plan
│   ├── SPEC_TEMPLATE.md       # Standard specification template
│   ├── conventions.md         # ID conventions and Definition of Done
│   └── phase-00/ ... phase-06/ # Completed/current/future detailed specifications
│
├── data/                 # Data directory structure (data excluded from git)
│   ├── raw/              # Immutable raw datasets
│   ├── interim/          # Intermediate transformed data
│   ├── processed/        # Canonical datasets for training/eval
│   └── external/         # External reference standards/metadata
│
├── configs/              # Structured YAML/JSON configuration files
│   ├── data/             # Dataset configs
│   ├── models/           # Architecture definitions
│   ├── training/         # Hyperparameters and training schedules
│   ├── evaluation/       # Evaluation protocols and thresholds
│   ├── inference/        # Runtime inference settings
│   └── deployment/       # Service configurations
│
├── src/                  # Core Python package source code
│   ├── data/             # Ingestion, validation, splitting, FUSeg loader, EDA
│   ├── segmentation/     # Dataset, U-Net + ResNet U-Net, augmentation, trainers, inference, metrics
│   ├── preprocessing/    # (placeholder)
│   ├── detection/        # (placeholder; optional backlog)
│   ├── inference/        # P03-S01 engine (pinned checkpoint, typed errors) + end-to-end pipeline
│   ├── quality/          # P03-S02 image quality gate
│   ├── measurement/      # P03-S03 area, perimeter, Feret, components, calibration
│   ├── longitudinal/     # P04 records, comparison policy, technical trends
│   ├── storage/          # P05-S02 SQLite migrations + content-addressed blob store
│   ├── api/              # P05-S01 FastAPI service, schemas, mask/overlay rendering
│   ├── dashboard/        # P05-S03 static dashboard (served at /dashboard)
│   ├── evaluation/       # (placeholder; metrics live in segmentation/)
│   └── utils/            # (placeholder)
│
├── tests/                # Automated test suites
│   ├── unit/             # Phase 00–02
│   ├── integration/      # P03 inference + pipeline
│   ├── quality/, measurement/, longitudinal/, api/, release/   # P03–P06
│   └── conftest.py       # tiny random-weight model fixture (no checkpoint needed)
│
├── experiments/          # Experiment tracking, notes, and configs
├── scripts/              # Standalone utility and automation scripts
├── notebooks/            # Exploratory research notebooks
├── models/               # Model checkpoints, exports, and metadata
├── outputs/              # Model predictions, benchmark artifacts, and visualizations
├── reports/              # Detailed evaluation, error analysis, and milestone reports
├── api/, database/, frontend/, docker/   # (placeholders; the service lives in src/api, src/storage, src/dashboard)
└── docs/                 # In-depth architectural, dataset, and design documentation
```
