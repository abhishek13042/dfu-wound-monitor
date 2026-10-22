# Historical Archive — P02-DEMO-SYNTHETIC-LEAKED

**Archive purpose:** Preserve the prior Phase 02 synthetic demonstration as
historical evidence.  
**Scientific status:** **SYNTHETIC DEMO / LEAKAGE-CONTAMINATED / NOT VALID FOR
GENERALIZATION**  
**Original experiment ID:** `P02-baseline-unet-bce-dice-v1`  
**Original execution date:** 2026-10-06  

This archive is retained because the prior report must remain auditable. Its
numbers are not real-data baseline metrics and must not be used for model
comparison, generalization, or clinical claims.

## Original reported setup

- Task: binary wound segmentation.
- Dataset label: DFUC2022, but the local files were synthetic demo data.
- Samples: 20 total, split 14 train / 3 validation / 3 test.
- Model: four-level Lightweight U-Net.
- Parameters: 3,350,273 trainable parameters.
- Loss: combined BCE + Dice.
- Original recorded checkpoint: epoch 10, validation Dice 1.0000.
- Original training log contains 20 completed epochs.
- Original configured train augmentation includes synchronized horizontal flip
  with probability 0.5.

## Original reported results

The prior evaluation JSON recorded, for three synthetic test samples:

| Metric | Historical value |
|---|---:|
| Mean Dice | 1.0000 |
| Mean IoU | 1.0000 |
| Mean Precision | 1.0000 |
| Mean Recall | 1.0000 |
| Mean test loss | 0.286059 |

All three displayed samples were classified as `GOOD`, with `TP=10,000`,
`FP=0`, and `FN=0` in the historical evaluation artifact.

## Contamination finding

All 20 local demo image files share the SHA-256 checksum
`5ba23a8923901235da470fce7bcf18ccbbc6bd4f0086169cb9e58e2281f89006`. The
manifest records:

- `checksum_leakage_detected: true`;
- `leakage_test_passed: false`;
- checksum overlap across train/validation/test;
- no verified patient-level isolation.

The masks also depict the same centered synthetic square. The reported perfect
metrics are therefore reproducible properties of a duplicated toy fixture, not
evidence of performance on real DFUC2022 images.

## Preserved source artifacts

- `configs/training/baseline_segmentation.json`
- `data/manifests/dataset_manifest.json`
- `data/manifests/quality_validation_report.json`
- `reports/ingestion_report.json`
- `reports/eda_summary.json`
- `reports/evaluation/P02-baseline-unet-bce-dice-v1_test_results.json`
- `reports/experiments/P02-baseline-unet-bce-dice-v1_training_log.json`
- `models/checkpoints/P02-baseline-unet-bce-dice-v1_best_val_dice.pth`
- `outputs/visualizations/phase_02_qualitative/`
- `reports/experiments/phase_02_debug_review.md`

The current SPEC-02-01 engineering report is
`reports/experiments/phase_02_baseline_report.md`. This archive remains
strictly historical and is excluded from FUSeg2021 evidence and metrics.
