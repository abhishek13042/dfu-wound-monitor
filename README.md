# DFU-WoundMonitor

**Computer Vision–Based Longitudinal Diabetic Foot Wound Monitoring System**

## Status

**Project Status:** Project setup / specification phase (Phase 00).  
**Implementation:** Not started.  
**Datasets:** Not downloaded.  
**Models:** Not trained.  

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
- **Computer Vision & Deep Learning**: Semantic segmentation, wound detection/localization, and image quality assessment.
- **Quantitative Measurement**: Area and boundary tracking over time.
- **Longitudinal Image Analysis**: Change detection and trajectory evaluation across examination visits.
- **Engineering Rigor**: Spec-driven development, modular architecture, robust testing, API design, database modeling, deployment, and error analysis.

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

---

## Repository Structure

```
dfu-wound-monitor/
├── README.md             # Project overview, medical disclaimer, and workflow
├── LICENSE               # Project licensing terms
├── .gitignore            # Git exclusion rules (data, weights, artifacts)
├── pyproject.toml        # Build configuration and project metadata
├── requirements.txt      # Core Python dependencies
├── Makefile              # Development, linting, testing, and lifecycle shortcuts
│
├── specs/                # Source of truth: specifications, tracker, traceability
│   ├── MASTER_TRACKER.md # Phase and specification progress tracking
│   ├── TRACEABILITY.md   # Requirement-to-evidence matrix
│   ├── SPEC_TEMPLATE.md  # Standard specification template
│   ├── conventions.md    # ID conventions and Definition of Done
│   └── phase-00/ ... phase-12/
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
│   ├── data/             # Ingestion, validation, and dataset loaders
│   ├── preprocessing/    # Normalization, resizing, color correction
│   ├── detection/        # Wound localization modules
│   ├── segmentation/     # Tissue and wound boundary segmentation
│   ├── measurement/      # Calibration and quantitative geometry engine
│   ├── quality/          # Image quality assessment (blur, illumination)
│   ├── longitudinal/     # Multi-visit alignment and trajectory tracking
│   ├── evaluation/       # Evaluation metrics and validation suites
│   ├── inference/        # Inference pipeline orchestration
│   └── utils/            # Shared utilities and logging
│
├── tests/                # Automated test suites
│   ├── unit/             # Unit tests
│   ├── integration/      # End-to-end and subsystem integration tests
│   ├── data/             # Data integrity tests
│   ├── detection/        # Detection module tests
│   ├── segmentation/     # Segmentation module tests
│   ├── measurement/      # Measurement engine tests
│   ├── quality/          # Quality assessment tests
│   ├── longitudinal/     # Longitudinal tracking tests
│   ├── api/              # API contract and integration tests
│   └── fixtures/         # Test fixtures and synthetic stubs
│
├── experiments/          # Experiment tracking, notes, and configs
├── scripts/              # Standalone utility and automation scripts
├── notebooks/            # Exploratory research notebooks
├── models/               # Model checkpoints, exports, and metadata
├── outputs/              # Model predictions, benchmark artifacts, and visualizations
├── reports/              # Detailed evaluation, error analysis, and milestone reports
├── api/                  # Backend REST API (FastAPI service structure)
├── database/             # Relational schemas, migrations, and seed scripts
├── frontend/             # Monitoring dashboard application
├── docker/               # Containerization configurations
└── docs/                 # In-depth architectural, dataset, and design documentation
```
