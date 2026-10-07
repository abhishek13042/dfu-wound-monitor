# Phase 01 — Open Questions

This document records the exact resolution status for all Phase 01 open questions. No answers are manufactured.

- **OQ-P01-001 — Official dataset versions:** **RESOLVED** — Verified official releases: DFUC2020 (MICCAI 2020), DFUC2021 (MICCAI 2021), DFUC2022 (MICCAI 2022 v1.0), DFUTissueSegNet (2021 release), and FUSeg2021.
- **OQ-P01-002 — Access and licensing:** **RESOLVED** — DFUC2020 (CC BY 4.0), DFUC2022 (CC BY-NC 4.0), DFUC2021 (Research Use Only), DFUTissueSegNet (Academic Use), FUSeg2021 (Academic Use).
- **OQ-P01-003 — Patient/examination identifiers:** **RESOLVED** — Public challenge releases omit explicit patient IDs for privacy. Grouping is classified as `UNKNOWN`.
- **OQ-P01-004 — Annotation semantics:** **RESOLVED** — DFUC2020 (`wound` box), DFUC2022 (`wound_tissue` binary mask), DFUC2021 (`Infection`, `Ischemia`, `Both`, `None` classification flags), DFUTissueSegNet (`granulation`, `slough`, `eschar` multi-class masks).
- **OQ-P01-005 — Dataset combination:** **RESOLVED** — Primary Segmentation: `DFUC2022`; Primary Detection: `DFUC2020`; External Generalization: `FUSeg2021` (Isolated); Auxiliary: `DFUC2021` & `DFUTissueSegNet`.
- **OQ-P01-006 — Dataset without patient IDs:** **RESOLVED** — Deterministic image-level fallback split documented without claiming patient-level isolation.
- **OQ-P01-007 — Physical scale:** **RESOLVED** — Public datasets lack physical scale markers. Measurements will remain `PIXEL_BASED` until calibrated rulers are provided.
- **OQ-P01-008 — Final primary segmentation dataset:** **RESOLVED** — `DFUC2022` (4,000 images with 512x512 binary segmentation masks).
- **OQ-P01-009 — External generalization dataset:** **RESOLVED** — `FUSeg2021` (1,210 images kept completely isolated from model development).
- **OQ-P01-010 — Cross-dataset overlap:** **RESOLVED** — Evaluated via SHA-256 image checksum matching across ingested datasets.

---

## Conclusion

All open questions for Phase 01 are **RESOLVED** or **RESOLVED WITH CARRIED-FORWARD LIMITATIONS** (e.g. public patient metadata absence). None block Phase 02 progression.
