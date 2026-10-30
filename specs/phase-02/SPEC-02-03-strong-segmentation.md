# SPEC-02-03 — Pretrained Segmentation Model and Honest Held-Out Evaluation

## Status

`COMPLETED` (2026-10-22). The Kaggle T4 run finished: best epoch 71, 53 min.
- Held-out test (191 images, frozen threshold 0.40 and area 128):
  - pooled Dice 0.922, macro Dice 0.841, non-empty Dice 0.853;
  - HD95 median 3.28 px.
- LowerLimb V3 external macro Dice: 0.268.
- Every metric was independently recomputed on a local CPU and agrees to within
  2.5e-5 (HD95 mean to within 0.004 px).

Full record, error review and limitations:
`reports/experiments/spec_02_03_report.md`. Checkpoint SHA-256:
`26aca52e401f23b5781d2596d74c1fd7fa86a6af0ab9fb3db9fa17dcffb5cf04`.

## Objective

Replace the from-scratch SPEC-02-01 U-Net with a competitive, literature-grade
segmentation model and measure it with an evaluation protocol that cannot leak
test information into model or post-processing selection.

SPEC-02-01 stays the frozen engineering baseline. Its config, validator
(`src/segmentation/config.py`) and tests are unchanged.

## Scope

- Derive a held-out split from FUSeg2021 (official validation → test).
- Detect near-duplicate images and use them as groups for the split.
- Train an ImageNet-pretrained ResNet34 U-Net at the native 512×512 resolution
  with strong synchronized augmentation.
- Tune the threshold and minimum component area on internal validation only,
  then evaluate the held-out test split once.
- Report macro, pooled, non-empty-subset and boundary (HD95) metrics.
- Run an external, no-tuning evaluation on LowerLimbFeetWound V3.

## Non-Goals

- Tissue-type segmentation (DFUTissue) or multi-class output.
- Claims of clinical efficacy.
- Use of FUSeg2021 public test images. Their masks are unreleased, so they
  have split `unlabeled_test` and are never used for supervision.

## Requirements

- **REQ-SPEC-02-03-001 (held-out split).** Official FUSeg2021 validation SHALL
  be the held-out `test` split. Internal validation SHALL be a seeded
  (seed 42, 15%) subset of official train.
- **REQ-SPEC-02-03-002 (near-duplicate grouping).** Images with a 64-bit DCT
  pHash Hamming distance ≤ 8 SHALL form groups. Each group lands entirely on
  one side of the train/internal-val split.
- **REQ-SPEC-02-03-003 (test-neighbour quarantine).** Official-train images that
  are near-duplicates of a held-out test image SHALL be quarantined
  (`issue_category = near_duplicate_of_heldout_test`).
- **REQ-SPEC-02-03-004 (selection isolation).** Checkpoint selection, early
  stopping, the threshold and the minimum component area SHALL use internal
  validation only. The test split SHALL NOT be loaded during training
  (`test_evaluation = NOT_RUN_DURING_TRAINING`).
- **REQ-SPEC-02-03-005 (native-resolution scoring).** Predicted probabilities
  SHALL be resized to each image's native size and scored against the
  original, unresized mask.
- **REQ-SPEC-02-03-006 (metrics).** Results SHALL report all of:
  - macro per-image Dice/IoU/precision/recall;
  - pooled (dataset-level) Dice/IoU;
  - non-empty-subset Dice/IoU and the empty-image false-positive rate;
  - HD95, with undefined cases counted.
- **REQ-SPEC-02-03-007 (external check).** LowerLimb V3 SHALL be evaluated with
  post-processing frozen from FUSeg internal validation, with no tuning on
  external data. LowerLimb images within Hamming 8 of any FUSeg image SHALL be
  excluded.
- **REQ-SPEC-02-03-008 (reproducibility).** The experiment record SHALL contain
  the resolved config, manifest version and split counts, the environment, and
  the reproducibility statement.

## Held-Out Split (implemented)

Manifest: `data/manifests/fuseg2021_heldout_manifest.json` (`fuseg2021-heldout-v1`).
It is built by `scripts/data/build_fuseg2021_heldout_manifest.py` and the split
report is `data/manifests/fuseg2021_heldout_split_report.json`.

| Split | Source | Samples | Empty masks |
|---|---|---|---|
| train | official train | 668 | 15 |
| val (internal) | official train, seeded, group-aware | 118 | 3 |
| test (held-out) | official validation | 191 | 5 |
| excluded | train near-duplicates of test | 7 | — |

Exact-checksum leakage between all three splits is zero. This is verified by
`verify_split_leakage` and by `tests/unit/test_spec_02_03.py`.

### Near-duplicate evidence and the patient-overlap limitation

- Threshold 8 was chosen by visual review. The reviewed pairs at distance ≤ 8
  were the same wound photographed again. Distance 10 introduced unrelated
  pairs. Every observed distance is even, and the pairs found sit at 6 (4
  pairs) and 8 (10 pairs).
- Result: 14 pairs forming 13 multi-image groups (the largest has 3 images).
  6 groups cross official train and validation. Their 7 official-train
  members were quarantined: train/0023, 0200, 0244, 0440, 0524, 0649 and
  0808.
- **Important finding:** the official FUSeg2021 train and validation splits
  share patients. For example, train/0023, train/0200 and validation/0375
  show the same wound. pHash only catches near-identical re-shots. It cannot detect the same
  patient photographed on a different day. FUSeg2021 has no patient IDs, so
  patient-level isolation **cannot be claimed**.
- Held-out scores may therefore be optimistic for truly unseen patients. The
  same limitation applies to every published FUSeg validation number. The
  LowerLimb external evaluation is the check against this.

## Model and Training (implemented)

| Item | Choice | Code |
|---|---|---|
| Architecture | U-Net decoder on an ImageNet-pretrained ResNet34 encoder | `src/segmentation/resnet_unet.py` |
| Input | 512×512 (native FUSeg size), ImageNet normalization | config |
| Augmentation | flips, rot90, affine, colour jitter, blur; image and mask transformed together | `src/segmentation/augmentation.py` |
| Loss | 0.5·BCE + 0.5·soft Dice | `src/segmentation/model.py` |
| Optimizer | AdamW 3e-4, encoder LR ×0.3, weight decay 1e-4 | `src/segmentation/strong_trainer.py` |
| Schedule | 3-epoch linear warmup → per-iteration cosine decay to 1% | same |
| Stability | AMP (CUDA), gradient clipping 1.0, EMA 0.999 with decay warmup | same |
| Budget | 100 epochs, batch size 8, early-stopping patience 25 | config |
| Selection | max internal-val macro Dice at threshold 0.5, using EMA weights | same |

Config: `configs/training/segmentation_resnet34_unet_512.json`. It is checked
by `src/segmentation/config_strong.py`, which rejects any test-split tuning or
selection.

## Evaluation Protocol (implemented)

1. Load the best (EMA) checkpoint.
2. Predict internal val with flip TTA at native resolution. Grid-search the
   threshold (0.30–0.70) and minimum component area (0–512 px), maximizing
   macro Dice. Ties go toward threshold 0.5 and less post-processing.
3. Freeze those values. Write `postprocessing_tuning.json`.
4. Score the held-out test split **once**. Write
   `heldout_test_evaluation.json`. Results at threshold 0.5 with no
   post-processing are recorded alongside, for transparency.
5. Score LowerLimb V3 using the frozen values. Write
   `lowerlimb_external_evaluation.json`.

## External Dataset Preparation (implemented)

`scripts/data/build_lowerlimb_external_manifest.py` produces
`data/manifests/lowerlimb_v3_external_manifest.json`:

- 2,686 image/mask pairs and no unpaired files.
- 322 masks differ in size from their image (224×224 against 331×331). These
  are nearest-resized to the image size at evaluation time; raw files are
  never modified.
- JPEG mask artefacts are binarized at ≥128.
- 1 image was excluded as a near-duplicate of a FUSeg image (Hamming ≤ 8).
  2,685 images are evaluable.
- The licence is `NOT_VERIFIED`. The dataset is used for a research-only
  external check and is not redistributed.

`scripts/data/check_near_duplicates.py` produces a cross-dataset near-duplicate
report for any set of image directories.

## Commands

Local (CPU) build steps; both have already been run, and their outputs are in `data/manifests/`:

```bash
python scripts/data/build_fuseg2021_heldout_manifest.py
python scripts/data/build_lowerlimb_external_manifest.py
```

Kaggle (GPU), with the repository and both datasets attached:

```bash
python scripts/training/run_spec_02_03.py --train --evaluate --external \
    --data-root "/kaggle/input/<fuseg>/Foot Ulcer Segmentation Challenge" \
    --external-data-root "/kaggle/input/<lowerlimb>/V3/extracted" \
    --output-root /kaggle/working/spec-02-03
```

To resume after an interruption, add
`--resume-checkpoint /kaggle/working/spec-02-03/checkpoints/resnet34_unet_512_latest.pth`.

Automated launch from the local machine (Kaggle CLI must already be
authenticated). This uploads three private datasets (code, FUSeg2021
train+validation, LowerLimb V3), pushes the private GPU kernel
`scripts/training/kaggle/spec_02_03_kernel.py`, waits, and downloads the outputs to
`reports/experiments/spec-02-03/kaggle/`:

```bash
python scripts/training/kaggle/launch_kaggle_spec_02_03.py --username <kaggle-user> --all
```

## Tests and Acceptance

Unit tests are in `tests/unit/test_spec_02_03.py` and run on CPU with
`pretrained=False`. They cover:

- pHash and grouping;
- held-out derivation guards;
- committed-manifest leakage;
- pooled, non-empty and HD95 metrics;
- model shapes;
- augmentation determinism;
- the dataset augmenter hook;
- post-processing and tuning;
- the LR schedule;
- EMA warmup;
- config rejection rules;
- a CPU train + resume smoke run.

An end-to-end CLI smoke run (64px, 2 epochs, random init) has completed on
real data through train → tune → test → external.

`COMPLETED` requires all of the following:

- the Kaggle run finishes;
- every output listed under Evaluation Protocol exists;
- the experiment record contains the metrics from REQ-SPEC-02-03-006;
- the report states the patient-overlap limitation.

## Reproducibility and Limitations

- Seeds are fixed and recorded, with `deterministic=false` (cuDNN autotune +
  AMP). Reruns agree closely but not bit-for-bit.
- No patient identifiers exist (see the near-duplicate section above).
- Technical segmentation metrics do not establish clinical efficacy.
