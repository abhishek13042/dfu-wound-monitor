# Dataset Source Verification Report (P01-S01)

> **Revision 2 — 2026-10-21.** Revision 1 (2026-10-06) marked all five
> candidate datasets as VERIFIED, named DFUC2022 as the primary segmentation
> dataset, and contained incorrect sources, counts and classes for FUSeg2021
> and DFUTissueSegNet. Those statements were not supported by acquired data.
> This revision is aligned with `reports/dataset_acquisition_report.md`
> (2026-10-08) and `data/external/dataset_registry.json` v2.0.0. The old text
> remains in git history.

## Status vocabulary

| Status | Meaning |
|---|---|
| VERIFIED | Checked against acquired files or the official source. |
| PARTIAL | Acquired, but with documented defects. |
| BLOCKED | Access route known; data not acquired. |
| NOT_VERIFIED | Not checked against the official source. |
| UNKNOWN | Not available from the official source. |

## Dataset table

| Dataset | Source / citation | Version | Contents (verified) | Annotation | Patient IDs | Role | Status |
|---|---|---|---|---|---|---|---|
| **FUSeg2021** | Wang et al., Sci Rep 2020; FUSeg 2021 challenge; github.com/uwm-bigdata/wound-segmentation | commit `42a272d` | 810 train + 200 val pairs; 200 unlabeled test; 512×512 PNG | Binary wound mask | UNKNOWN | **Primary segmentation** | VERIFIED (license terms NOT_VERIFIED) |
| **DFUTissueSegNet** | Dhar et al. 2024, arXiv:2406.16012; github.com/uwm-bigdata/DFUTissueSegNet | commit `d2f6e72` | 110 labeled (94 train/val + 16 test); 600 unlabeled | Tissue masks (granulation, callus, fibrin focus) | UNKNOWN | Optional tissue extension | VERIFIED (license NOT_VERIFIED) |
| **LowerLimbFeetWound V3** | Mendeley Data DOI 10.17632/hsj38fwnvr.3 | V3, 2026-02-11 | 8,129 JPG; 2,686 wound/mask pairs | Binary wound mask | UNKNOWN | Candidate external evaluation | PARTIAL (322 mask dimension mismatches) |
| **Medetec** | medetec.co.uk | snapshot 2026-10-08 | 610 JPG | None | UNKNOWN | Qualitative OOD / quality-gate fixtures | VERIFIED |
| **DFUC2022** | DFUC2022 challenge, MMU | — | not acquired | Binary mask (per challenge, NOT_VERIFIED) | UNKNOWN | Blocked candidate | BLOCKED |
| **DFUC2020** | DFUC2020 challenge, MMU | — | not acquired | Bounding boxes (NOT_VERIFIED) | UNKNOWN | Blocked candidate (detection optional) | BLOCKED |
| **DFUC2021** | DFUC2021 challenge, MMU | — | not acquired | Image-level classes (NOT_VERIFIED) | UNKNOWN | Out of MVP scope | BLOCKED |

## Dataset mapping (current)

1. **Primary segmentation:** FUSeg2021.
   - The official train split is used for training.
   - The official validation split is used for checkpoint selection.
   - The public test split has no labels, so no test metric can be reported. See SPEC-02-02.
2. **External / out-of-distribution evaluation (planned):** LowerLimbFeetWound V3 for quantitative evaluation, after the preprocessing decision. Medetec for qualitative review.
3. **Optional extension:** DFUTissueSegNet. It shares the AZH clinical source with FUSeg2021, so it is *not* an independent external set.
4. **Blocked:** DFUC2020, DFUC2021 and DFUC2022, until the DFU license application is approved.

## Governance notes

- **Patient metadata:**
  - No acquired dataset provides patient identifiers.
  - All splits are image-level, and no patient-level isolation is claimed.
- **Physical scale:**
  - No dataset provides calibration markers.
  - All measurements are `PIXEL_BASED` until a calibration specification exists.
- **Semantic independence:**
  - Datasets keep separate schemas.
  - No label merging is performed.
- **Overlap:**
  - Byte-identical duplicates were checked with SHA-256.
  - Near-duplicate checks (perceptual hash) are still open (OQ-P01-010).
