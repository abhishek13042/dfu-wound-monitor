# Data Directory

This directory contains the dataset storage structure for DFU-WoundMonitor.

## Directory Structure

- `raw/`: Immutable, original raw images and annotations directly from source datasets.
- `interim/`: Intermediate transformations, staged conversions, or unstandardized splits.
- `processed/`: Canonical, preprocessed, validated, and normalized datasets formatted for training and evaluation pipelines.
- `external/`: External reference standards, third-party metadata, calibration charts, or baseline masks.

## FUSeg2021 SPEC-02-01 Input Contract

The primary segmentation dataset for SPEC-02-01 is **FUSeg2021**. The verified
official source is preserved at:

```text
data/raw/FUSeg2021/source/data/Foot Ulcer Segmentation Challenge/
├── train/images/       # 810 RGB images
├── train/labels/       # 810 binary wound masks
├── validation/images/  # 200 RGB images
├── validation/labels/  # 200 binary wound masks
└── test/images/        # 200 RGB images; public masks unavailable
```

The machine-readable contract is `configs/data/fuseg2021.json`. Build or
rebuild the manifest with:

```bash
python scripts/build_fuseg2021_manifest.py
```

The builder preserves the official split directories, records image/mask
quality, reports patient-ID absence, quarantines exact duplicate images, and
fails if cross-split leakage remains. It does not download a mirror or fall
back to the synthetic smoke fixture. The public test images are inputs only;
without usable masks they are excluded from supervised training and evaluation.

### Held-out manifest (SPEC-02-03)

The official manifest has no labeled test split, so SPEC-02-03 derives one.
The official manifest itself is never modified:

```bash
python scripts/build_fuseg2021_heldout_manifest.py      # ~1.5 min (pHash)
```

This writes `data/manifests/fuseg2021_heldout_manifest.json`
(`fuseg2021-heldout-v1`) and `fuseg2021_heldout_split_report.json`:

| Split | Source | Samples |
|---|---|---|
| `train` | official train | 668 |
| `val` (internal) | official train, seed 42, 15%, near-duplicate-group-aware | 118 |
| `test` (held-out) | official validation | 191 |
| `excluded` | train near-duplicates of a test image (pHash Hamming ≤ 8) | 7 |
| `unlabeled_test` | official public test (no masks) | 200 |

FUSeg2021 has no patient IDs, and the official train and validation splits
visibly share patients. Near-duplicate grouping removes only near-identical
re-shots, so patient-level isolation is not claimed.

### LowerLimbFeetWound V3 external manifest

```bash
python scripts/build_lowerlimb_external_manifest.py
```

This writes `data/manifests/lowerlimb_v3_external_manifest.json` (2,686 pairs;
2,685 evaluable after excluding 1 FUSeg near-duplicate). 322 masks are 224×224
for 331×331 images; they are nearest-resized to the image size at evaluation
time, and the raw files are untouched. The licence is not verified, so the
dataset is used only for an external, no-tuning check.

To check near-duplicates across any image collections:

```bash
python scripts/check_near_duplicates.py --collection NAME=DIR [--collection NAME=DIR ...]
```

## Other acquired and blocked datasets

Full details are in `external/dataset_registry.json` (v2.0.0) and
`../reports/dataset_acquisition_report.md`.

| Dataset | Local path | Status | Intended use |
|---|---|---|---|
| LowerLimbFeetWound V3 | `raw/LowerLimbFeetWound/V3/` | Acquired; 322 mask dimension mismatches | Candidate external evaluation |
| Medetec | `raw/MedetecWoundDatabase/source/` | Acquired; images only, no masks | Qualitative OOD review, quality-gate fixtures |
| DFUTissueSegNet | `raw/DFUTissueSegNet/source/DFUTissue/` | Acquired; 110 labeled + 600 unlabeled | Optional tissue extension (same AZH source as FUSeg) |
| DFUC2020 / 2021 / 2022 | `raw/DFUC2022/` (empty) | **BLOCKED**, license application required | None until approved |

## Important Policies

1. **No Large Data in Version Control**:
   All image data, binary masks, and large annotations are excluded from Git via `.gitignore`.
2. **Immutable Raw Data**:
   Files placed in `raw/` are treated as read-only. Any transformations or cleanings must write to `interim/` or `processed/`.
3. **Traceability**:
   Dataset provenance, versioning, licenses, splits, and acquisition scripts are formally specified in Phase 01 (Dataset & Data Engineering).
4. **Acquisition Status**:
   No datasets were acquired during Phase 00. Acquisition happened on 2026-10-08 under Phase 01 (see the table above).
