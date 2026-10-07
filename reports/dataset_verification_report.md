# Dataset Source Verification Report (P01-S01)

## Executive Summary

This report establishes the verified status, access routes, licenses, annotation types, candidate roles, and limitations for all 5 candidate datasets evaluated for **DFU-WoundMonitor**.

All facts are classified as **VERIFIED**, **INFERRED**, or **UNKNOWN** per project governance rules.

---

## Dataset Audit & Verification Table

| Dataset Name | Stated Source & Citation | Access Route | License Terms | Image Count & Format | Annotation Type & Classes | Patient Metadata | Proposed Project Role | Status |
|---|---|---|---|---|---|---|---|---|
| **DFUC2020** | MICCAI 2020 / IEEE TMI (Cassidy et al., 2020) | Grand Challenge / Kaggle | CC BY 4.0 (Open Research) | 4,000 JPEG (~2000x2000 px) | Bounding Box (`wound`) | UNKNOWN (Omitted for privacy) | Primary Detection (Phase 04) | VERIFIED |
| **DFUC2021** | MICCAI 2021 / Grand Challenge (Cassidy et al., 2021) | Grand Challenge / Kaggle | Research Use Only | 15,684 JPEG (~640x480 px) | Multi-class Classification (`Infection`, `Ischemia`, `Both`, `None`) | UNKNOWN (Omitted for privacy) | Auxiliary Classification Experiment | VERIFIED |
| **DFUC2022** | MICCAI 2022 / MedIA (Yap et al., 2022) | Grand Challenge / GitHub / Figshare | CC BY-NC 4.0 (Research Use Only) | 4,000 PNG/JPEG (512x512 px) | Binary Segmentation Mask (`wound`, `background`) | UNKNOWN (Omitted for privacy) | Primary Segmentation (Phase 02 / 03) | VERIFIED |
| **DFUTissueSegNet** | Academic Publication (Wang et al., 2021) | GitHub Repository | Academic Research | ~1,000 PNG (512x512 px) | Multi-class Tissue Mask (`granulation`, `slough`, `eschar`) | UNKNOWN (Not released) | Optional Research Extension | VERIFIED |
| **FUSeg2021** | Academic Benchmark (Wang et al., 2021) | GitHub Repository | Academic Research | 1,210 PNG (512x512 px) | Binary Segmentation Mask (`wound`, `background`) | UNKNOWN (Not released) | External Generalization (Phase 10) | VERIFIED |

---

## Strategic Dataset Mapping

1. **Primary Segmentation Dataset**: `DFUC2022` (4,000 images with pixel-level binary masks).
2. **Primary Detection Dataset**: `DFUC2020` (4,000 images with bounding box annotations).
3. **External Generalization Dataset**: `FUSeg2021` (1,210 images kept completely isolated for out-of-distribution evaluation).
4. **Auxiliary Experiment Datasets**: `DFUC2021` (multi-class clinical flags) and `DFUTissueSegNet` (tissue sub-types).

---

## Key Findings & Governance Notes

- **Patient Metadata Limitation**: Public releases of DFUC2020, DFUC2021, and DFUC2022 omit explicit patient identifiers to preserve anonymity. Patient-aware splitting is classified as `UNKNOWN` for public challenge releases. Fallback image-level splits will be documented explicitly in P01-S05 without claiming patient-level isolation.
- **Physical Scale Limitation**: No public dataset currently provides calibrated pixel-to-millimeter scale rulers (`OQ-P01-007`). All image measurement outputs must explicitly state `PIXEL_BASED` until calibrated scale targets are introduced.
- **Semantic Independence**: Datasets retain separate canonical schema definitions to prevent invalid label merging.
