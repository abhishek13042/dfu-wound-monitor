# SPEC-02-01 — Baseline Engineering Implementation (FUSeg2021)

## Status

`COMPLETED` (engineering gate PASS). Multi-epoch GPU training is intentionally
owned by SPEC-02-02.

> This file was written retroactively on 2026-10-21. Before then, SPEC-02-01
> was referenced from `MASTER_TRACKER.md`, `REVISED_ROADMAP.md` and
> `TRACEABILITY.md` but had no specification file. It records the scope that
> was actually delivered and does not add new requirements.

## Objective

Implement and verify the complete real-data baseline training pipeline for
binary wound segmentation on FUSeg2021, without running the full training
schedule.

## Scope

It consolidates P02-S01 (task and model selection), P02-S02 (preprocessing and
dataset interface) and P02-S03 (model), plus the bounded parts of P02-S04
(checkpoint and resume mechanics).

## Non-Goals

- Full multi-epoch training and reported metrics (SPEC-02-02).
- Evaluating the unlabeled FUSeg2021 public test images.
- Pretrained or advanced architectures, tissue analysis, Phase 03+ work.

## Requirements

### Data contract
- **REQ-SPEC-02-01-001:** The FUSeg2021 manifest SHALL preserve the official train/validation assignment and SHALL be built from the pinned source commit `42a272d`.
- **REQ-SPEC-02-01-002:** Pairs with exact duplicate images across splits, or with invalid mask values, SHALL be quarantined without modifying raw files.

### Preprocessing and model
- **REQ-SPEC-02-01-003:** Image and mask transforms SHALL be synchronized. Masks SHALL stay strictly binary after resizing (nearest-neighbour).
- **REQ-SPEC-02-01-004:** The model SHALL be a configurable four-level U-Net that outputs logits. The loss SHALL be BCE-with-logits plus soft Dice.

### Training controls
- **REQ-SPEC-02-01-005:** The best checkpoint SHALL be selected by validation Dice only.
- **REQ-SPEC-02-01-006:** Latest checkpoints SHALL support resume of model, optimizer, scheduler and RNG state.
- **REQ-SPEC-02-01-007:** Bounded real-data sanity checks SHALL demonstrate correct shapes, binary masks, a finite loss and finite gradients.
- **REQ-SPEC-02-01-008:** A single Kaggle entrypoint SHALL reproduce the run from configuration.

## Delivered design

| Item | Value |
|---|---|
| Data | FUSeg2021: 793 usable train / 191 usable val after quarantine |
| Input | 256×256, ImageNet normalization, horizontal flip |
| Model | LightweightUNet [16, 32, 64, 128], 838,785 parameters, random (Kaiming) init |
| Loss | 0.5·BCEWithLogits + 0.5·soft Dice |
| Optimizer | Adam 1e-3, ReduceLROnPlateau on val Dice |
| Schedule | 12 epochs, batch size 8 (configured; run under SPEC-02-02) |
| Metrics | Per-image Dice, IoU, precision, recall; macro mean; empty/empty = 1.0 |

## Implementation

The implementation lives in `src/data/fuseg.py` and `src/segmentation/`.

| Purpose | Path |
|---|---|
| Dataset config | `configs/data/fuseg2021.json` |
| Training config | `configs/training/baseline_segmentation_real.json` |
| Manifest builder | `scripts/data/build_fuseg2021_manifest.py` |
| Kaggle entrypoint | `scripts/training/kaggle/run_kaggle_spec_02_01.py` |

## Tests and Evidence

Tests:

- `tests/unit/test_spec_02_01_fuseg2021.py`
- `tests/unit/test_spec_02_01_engineering.py`
- `tests/unit/test_phase_02_baseline.py`
- `tests/unit/test_phase_02_execution_controls.py`

Evidence:

- `reports/experiments/P02-SPEC-02-01-fuseg2021_sanity_checks.json` (status PASS)
- `data/manifests/fuseg2021_quality_report.json`
- `reports/experiments/phase_02_baseline_decision_record.md`

## Limitations

- The model is not pretrained, and training is at 256 px, half the native 512 px.
- The design targets a reproducible baseline, not state-of-the-art accuracy.
- The official validation split is used for checkpoint selection, so it cannot also serve as an unbiased test set (see SPEC-02-02, *Evaluation split*).
- No patient identifiers are available, so the split is image-level.
