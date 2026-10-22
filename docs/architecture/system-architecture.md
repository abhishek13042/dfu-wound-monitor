# DFU-WoundMonitor — System Architecture & Component Contracts

## 1. Overview

This document defines the high-level architecture, module boundaries, data flow, and conceptual component contracts for the **DFU-WoundMonitor** system, as specified in `specs/phase-00/05-system-architecture.md`.

> **Revision note (2026-10-21).** This document is aligned with
> `specs/REVISED_ROADMAP.md`. Wound detection/localization is **optional**:
> full-image segmentation is the default path, and a detector is added only if
> evidence shows segmentation alone is inadequate. The database stores
> case/examination *references*, not identifiable patient records.

### Implementation status

| Component | Package | Owning spec | Status |
|---|---|---|---|
| Data ingestion, validation, splitting, EDA | `src/data/` | P01-S01..S06 | Implemented |
| Segmentation dataset, model, training, metrics | `src/segmentation/` | SPEC-02-01..03 | Implemented; SPEC-02-03 trained and verified (held-out pooled Dice 0.922) |
| Inference contract + end-to-end pipeline | `src/inference/` | P03-S01 | Implemented |
| Image quality gate | `src/quality/` | P03-S02 | Implemented (thresholds calibrated on FUSeg2021 train) |
| Measurement engine | `src/measurement/` | P03-S03 | Implemented |
| Records, comparison, trends | `src/longitudinal/` | P04-S01..S03 | Implemented (validated with constructed series only) |
| Persistence | `src/storage/` | P05-S02 | Implemented (SQLite + content-addressed blobs) |
| API | `src/api/` | P05-S01 | Implemented (FastAPI `/api/v1`) |
| Dashboard | `src/dashboard/` | P05-S03 | Implemented (static HTML, API-only) |
| Validation, benchmark, release | `scripts/evaluation/`, `scripts/deployment/` | P06-S01..S03 | Implemented; see `reports/final/` and `docs/release/RELEASE.md` |
| Detection/localization | `src/detection/` | Optional backlog | Placeholder package only; not on the default path |

### As-built request flow

```text
POST /api/v1/analyses (multipart image, optional examination_id, pixels_per_mm)
  -> InferenceEngine.decode     (format/size/EXIF checks; INPUT failure -> 400)
  -> QualityGate.evaluate       (REJECTED -> stored, 422, segmentation never runs)
  -> InferenceEngine.predict    (resize 512, flip TTA, threshold 0.40, min component 128 px, back to native size)
  -> measure()                  (PIXEL_BASED, or PHYSICALLY_CALIBRATED with pixels_per_mm)
  -> Database.save_analysis     (one transaction; image, mask and probability as content-addressed blobs)
  -> AnalysisResponse           (measurement, quality, provenance, warnings, limitations, artifact links)
GET /api/v1/cases/{id}/trend and /api/v1/compare apply the explicit CompatibilityPolicy.
```

Every error uses one envelope (`category`, `code`, `message`, `failure_class`), where
`failure_class` is INPUT, QUALITY, MODEL, PERSISTENCE or SERVICE.

---

## 2. Core Principles

1. **Strict Separation of Concerns**: Image quality assessment, optional localization, semantic segmentation, measurement calculation, API services, and user interfaces are decoupled into independent layers.
2. **Clinical Decision Support Boundary**: All model outputs are treated as technical image-derived parameters. No clinical diagnosis or autonomous treatment recommendations are generated.
3. **Traceability & Versioning**: Every inference output retains references to the model version, preprocessing configuration, and underlying input examination record.
4. **Data Contract Compliance**: Modules communicate through explicit schema contracts (e.g., Pydantic/dataclass structures) rather than untyped dictionaries or mutable global states.

---

## 3. High-Level System Architecture

```text
                               ┌───────────────────────────┐
                               │   User / Clinical Client  │
                               └─────────────┬─────────────┘
                                             │
                                             ▼
                               ┌───────────────────────────┐
                               │     Frontend Dashboard    │
                               │ (static HTML, API only)   │
                               └─────────────┬─────────────┘
                                             │
                                             ▼
                               ┌───────────────────────────┐
                               │       FastAPI REST        │
                               │      Application API      │
                               └─────────────┬─────────────┘
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       │                                           │
                       ▼                                           ▼
      ┌─────────────────────────────────┐        ┌──────────────────────────────────┐
      │     Computer Vision Engine      │        │       Relational Database        │
      │                                 │        │                                  │
      │  ┌───────────────────────────┐  │        │  - Case / Patient References     │
      │  │ Image Quality Assessment  │  │        │  - Examination Records           │
      │  └─────────────┬─────────────┘  │        │  - Image File References         │
      │                │                │        │  - Segmentations & Mask Paths    │
      │                ▼                │        │  - Measurements & Scales         │
      │  ┌───────────────────────────┐  │        │  - Model Versions & Configs     │
      │  │ [Optional] Localization   │  │        └──────────────────────────────────┘
      │  └─────────────┬─────────────┘  │
      │                │                │
      │                ▼                │
      │  ┌───────────────────────────┐  │
      │  │ Wound Segmentation        │  │
      │  └─────────────┬─────────────┘  │
      │                │                │
      │                ▼                │
      │  ┌───────────────────────────┐  │
      │  │ Post-processing           │  │
      │  └─────────────┬─────────────┘  │
      │                │                │
      │                ▼                │
      │  ┌───────────────────────────┐  │
      │  │ Measurement Engine        │  │
      │  └───────────────────────────┘  │
      └────────────────┬────────────────┘
                       │
                       ▼
      ┌─────────────────────────────────┐
      │     Longitudinal Comparison     │
      │       & Trajectory Analysis     │
      └─────────────────────────────────┘
```

---

## 4. Pipeline Stages & Responsibilities

### Stage 1: Image Quality Assessment (`src/quality/`)
- **Input**: Raw uploaded image (`H x W x C`, RGB format).
- **Function**: Assesses image blur, illumination variance, glare/reflections, and field-of-view adequacy.
- **Output**: Quality assessment score, binary acceptance status (`ACCEPTED` / `REJECTED`), and failure reason if rejected.

### Stage 2 (optional): Wound Localization (`src/detection/`)
- **Status**: Not on the default path. It is enabled only if an approved spec shows that full-image segmentation is inadequate, for example for very small wounds in high-resolution photos.
- **Input**: Accepted image (`H x W x C`).
- **Function**: Detects bounding boxes around wound candidate regions.
- **Output**: List of bounding boxes `[x_min, y_min, x_max, y_max]`, confidence scores, and crop regions.

### Stage 3: Wound Segmentation (`src/segmentation/`)
- **Input**: Full image tensor (`C x H x W`) by default. It is a crop only when optional localization is enabled.
- **Function**: Predicts a pixel-level wound boundary mask.
- **Output**: Binary mask `(H x W)` where 1 indicates wound and 0 indicates background. The mask is mapped back to the **original image resolution** before measurement.

### Stage 4: Measurement Engine (`src/measurement/`)
- **Input**: Binary segmentation mask `(H x W)` and optional calibration marker scale (`pixels_per_millimeter`).
- **Function**: Calculates pixel area, perimeter, bounding box dimensions, Feret diameters, components and physical metrics (mm, mm²) if a validated scale exists.
- **Output**: Structured measurement object containing area, perimeter, calibration status, and confidence metrics.

### Stage 5: Longitudinal Monitoring (`src/longitudinal/`)
- **Input**: Current examination record and earlier examination records that share an explicitly provided case reference. Identity is never inferred from filenames.
- **Function**: Computes area change ($\Delta \text{Area}$), percentage area change, and visual comparison overlays across visits. Physical-unit comparisons require calibration on both examinations.
- **Output**: Technical trend metrics and aligned multi-visit comparison views. These are not healing diagnoses.
- **Data note**: No acquired dataset contains longitudinal series, so this stage is validated with constructed multi-visit fixtures only (the same or different held-out images assigned to dated examinations).

---

## 5. Architectural Invariants

1. **Quality Failures Do Not Invoke Model Inference**: If an image fails quality checks, downstream localization (if enabled) and segmentation models are bypassed.
2. **Explicit Calibration Flags**: All measurement outputs must explicitly state whether dimensions are `PIXEL_BASED` or `PHYSICALLY_CALIBRATED`.
3. **No Direct UI-to-Model Coupling**: The frontend dashboard communicates exclusively via REST API endpoints.
