# Phase 01 — Open Questions

This document records the resolution status for all Phase 01 open questions.
No answers are manufactured.

> **Correction notice (2026-10-21).** The original resolutions (2026-10-06)
> named DFUC2022 as the primary segmentation dataset and FUSeg2021 as an
> isolated external set, and listed licenses and counts for the DFUC datasets
> as verified. The DFUC datasets were never acquired: they are **BLOCKED**
> pending the official DFU license application (see
> `reports/dataset_acquisition_report.md`). The entries below are corrected.
> The original wording is kept in git history.

| ID | Question | Status | Resolution |
|---|---|---|---|
| OQ-P01-001 | Official dataset versions | RESOLVED | FUSeg2021: uwm-bigdata/wound-segmentation commit `42a272d`. DFUTissueSegNet: uwm-bigdata/DFUTissueSegNet commit `d2f6e72`. LowerLimbFeetWound: Mendeley DOI 10.17632/hsj38fwnvr.3. Medetec: website snapshot 2026-10-08. DFUC2020/2021/2022: not acquired (BLOCKED). |
| OQ-P01-002 | Access and licensing | PARTIALLY RESOLVED | Medetec terms are recorded. FUSeg2021, DFUTissueSegNet and LowerLimb license terms must be recorded verbatim before any redistribution. DFUC terms will be known only after license approval. |
| OQ-P01-003 | Patient/examination identifiers | RESOLVED (limitation) | No acquired dataset provides patient identifiers. Grouping is `UNKNOWN`. |
| OQ-P01-004 | Annotation semantics | RESOLVED for acquired data | FUSeg2021: binary wound mask. DFUTissueSegNet: tissue masks (granulation, callus, fibrin focus). LowerLimb: binary wound masks, with 322 dimension mismatches. Medetec: no masks. DFUC: NOT_VERIFIED. |
| OQ-P01-005 | Dataset combination | SUPERSEDED → RESOLVED | No datasets are merged. Primary segmentation: **FUSeg2021**. Candidate external evaluation: LowerLimbFeetWound V3 and Medetec (qualitative only). DFUTissueSegNet: optional tissue extension, not independent of FUSeg because both come from AZH. DFUC: blocked candidates. |
| OQ-P01-006 | Dataset without patient IDs | RESOLVED (limitation) | Image-level split documented; no patient-level isolation is claimed. |
| OQ-P01-007 | Physical scale | OPEN (carried forward) | No acquired dataset has calibration markers. Measurements stay `PIXEL_BASED`. Physical units need a calibration spec (Phase 03). |
| OQ-P01-008 | Final primary segmentation dataset | SUPERSEDED → RESOLVED | **FUSeg2021** (810 train / 200 val / 200 unlabeled test; after quarantine, 793 / 191 usable). |
| OQ-P01-009 | External generalization dataset | SUPERSEDED → OPEN | FUSeg2021 is no longer external. The candidate is LowerLimbFeetWound V3, once the mask-dimension preprocessing decision is approved. |
| OQ-P01-010 | Cross-dataset overlap | OPEN | Exact SHA-256 matching only detects byte-identical files. Near-duplicate (perceptual hash) checks between FUSeg2021, DFUTissueSegNet and LowerLimb have not been run. |

---

## Conclusion

Phase 01 is complete for the acquired data. Two items are carried forward and
do not block SPEC-02-02:

- OQ-P01-007 (physical scale)
- OQ-P01-010 (near-duplicate overlap)

OQ-P01-009 must be resolved before any external-generalization claim is made.
