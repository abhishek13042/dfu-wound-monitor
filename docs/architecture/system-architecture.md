# DFU-WoundMonitor — System Architecture & Component Contracts

## 1. Overview

This document defines the high-level architecture, module boundaries, data flow, and conceptual component contracts for the **DFU-WoundMonitor** system, as specified in `specs/phase-00/05-system-architecture.md`.

---

## 2. Core Principles

1. **Strict Separation of Concerns**: Image quality assessment, object detection, semantic segmentation, measurement calculation, API services, and user interfaces are decoupled into independent layers.
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
                               │  (React / Monitoring UI)  │
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
      │  ┌───────────────────────────┐  │        │  - Patient Records               │
      │  │ Image Quality Assessment  │  │        │  - Examination Records           │
      │  └─────────────┬─────────────┘  │        │  - Image File References         │
      │                │                │        │  - Segmentations & Mask Paths    │
      │                ▼                │        │  - Measurements & Scales         │
      │  ┌───────────────────────────┐  │        │  - Model Versions & Configs     │
      │  │ Wound Detection/Loc.      │  │        └──────────────────────────────────┘
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

### Stage 2: Wound Detection / Localization (`src/detection/`)
- **Input**: Accepted image (`H x W x C`).
- **Function**: Detects bounding boxes around diabetic foot ulcer candidate regions.
- **Output**: List of bounding boxes `[x_min, y_min, x_max, y_max]`, confidence scores, and crop regions.

### Stage 3: Wound Segmentation (`src/segmentation/`)
- **Input**: Image crop or full image tensor (`C x H x W`).
- **Function**: Predicts pixel-level wound boundary mask.
- **Output**: Binary mask `(H x W)` where 1 indicates wound tissue and 0 indicates background.

### Stage 4: Measurement Engine (`src/measurement/`)
- **Input**: Binary segmentation mask `(H x W)` and optional calibration marker scale (`pixels_per_millimeter`).
- **Function**: Calculates pixel area, perimeter, bounding box dimensions, and physical metrics (cm²) if scale exists.
- **Output**: Structured measurement object containing area, perimeter, calibration status, and confidence metrics.

### Stage 5: Longitudinal Monitoring (`src/longitudinal/`)
- **Input**: Current examination record and historical examination records for the same patient.
- **Function**: Computes area change trajectory ($\Delta \text{Area}$), percentage healing rate, and visual comparison overlays across visits.
- **Output**: Trajectory trend metrics and aligned multi-visit comparison views.

---

## 5. Architectural Invariants

1. **Quality Failures Do Not Invoke Model Inference**: If an image fails quality checks, downstream detection and segmentation models are bypassed.
2. **Explicit Calibration Flags**: All measurement outputs must explicitly state whether dimensions are `PIXEL_BASED` or `PHYSICALLY_CALIBRATED`.
3. **No Direct UI-to-Model Coupling**: The frontend dashboard communicates exclusively via REST API endpoints.
