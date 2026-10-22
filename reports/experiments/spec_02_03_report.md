# SPEC-02-03 / SPEC-02-02 — Training, Held-Out Evaluation and Error Review

Experiment: `P02-SPEC-02-03-fuseg2021-resnet34-unet-512-v1`
Run: private Kaggle kernel `abhishekg14/dfu-spec-02-03` (version 1), finished 2026-10-21 21:40 UTC.
Raw outputs: `reports/experiments/spec-02-03/kaggle/spec-02-03/`.
Best checkpoint: `models/checkpoints/spec-02-03/resnet34_unet_512_best.pth`
(gitignored; SHA-256 `26aca52e401f23b5781d2596d74c1fd7fa86a6af0ab9fb3db9fa17dcffb5cf04`).

## 1. Run

| Item | Value |
|---|---|
| Hardware | 1× Tesla T4, 4 CPU, CUDA 12.8, PyTorch 2.11.0, Python 3.13 |
| Data | `fuseg2021-heldout-v1`: train 668, internal val 118, held-out test 191 |
| Epochs | 96 of 100 (early stop, patience 25) |
| Best epoch | 71 (EMA weights), internal-val macro Dice 0.879 at threshold 0.5 |
| Training time | 53.4 min (≈33 s per epoch) |
| Test split loaded during training | No (`NOT_RUN_DURING_TRAINING`) |

Training curve (internal val, macro Dice at 0.5): epoch 1: 0.291 · 11: 0.854 ·
31: 0.872 · 71: 0.879 (best) · 96: 0.872. Train loss kept falling while val
Dice plateaued after epoch ~30, so early stopping ended the run correctly.

## 2. Post-processing frozen on internal validation

Grid: threshold 0.30–0.70 × minimum component area {0, 64, 128, 256, 512}.
Selected **threshold 0.40, minimum area 128 px**. Internal val macro Dice
0.877 → 0.889. Empty-image false-positive rate 2/3 → 1/3.

## 3. Held-out test (official FUSeg2021 validation, 191 images, scored once)

| Metric | Frozen (0.40, area 128) — **primary** | Threshold 0.5, no post-processing (reference) |
|---|---|---|
| Pooled (dataset-level) Dice | **0.922** | 0.924 |
| Pooled IoU | 0.856 | 0.859 |
| Macro per-image Dice | **0.841** (std 0.243) | 0.864 (std 0.190) |
| Macro IoU | 0.778 | 0.796 |
| Macro precision / recall | 0.881 / 0.886 | 0.875 / 0.905 |
| Non-empty subset Dice (186 images) | 0.853 | 0.877 |
| Empty-image false-positive rate (5 images) | 3/5 | 3/5 |
| HD95 (px), median / mean (180 defined) | 3.28 / 18.5 | — |

The primary number is the frozen setting, because that is what the protocol
committed to before the test set was seen. The reference column is reported
for transparency only. **It must not be used to re-select post-processing**,
since that would tune on the test set.

Independent check: the held-out metrics were recomputed on a local CPU from
the downloaded checkpoint. See section 6.

### Comparison caveat

- The official FUSeg2021 train and validation splits share patients. pHash
  removed 7 near-identical re-shots, but it cannot detect the same patient
  photographed on another day.
- These held-out numbers are therefore likely optimistic for unseen patients.
- They are also not directly comparable with the FUSeg2021 challenge
  leaderboard, which was scored on the unreleased official test masks.

## 4. Error review (observed vs hypothesis)

The 11 test images that score Dice 0 fall into three groups.

**A. Tiny wounds deleted by post-processing (observed, 8 images).**
- Images 0456, 0580, 0730, 0816, 0904, 0955, 0798 and 0973 have ground-truth
  wounds of 20–857 px.
- The raw prediction marks the correct location, but small-component removal
  (128 px) deletes it, or the predicted fragments are each below 128 px. The
  final mask is empty.
- This is why the frozen setting scores lower on macro Dice (0.841) than the
  threshold-0.5 reference (0.864). Pooled Dice hardly changes (0.922 vs 0.924),
  because these wounds are tiny in pixel terms.
- Cause: the 118-image internal val set has few tiny wounds, so the area rule
  looked harmless there. *Fix for the next version, chosen without the test
  set:* tune post-processing with cross-validation over the full train split,
  or cap the minimum area relative to the largest predicted component.

**B. "Empty" ground truth that shows a visible ulcer (observed 2, hypothesis on cause).**
- Images 0417 and 0533 have empty masks, but the photo shows an obvious ulcer
  (0417: heel; 0533: plantar), and the model segments it.
- *Hypothesis:* these are annotation omissions. If so, the reported
  empty-image false-positive rate (3/5) overstates the model's error. The
  labels were **not** changed; this is recorded for the dataset owners.

**C. One further empty-mask image (0869)** has a false-positive prediction.
It was not reviewed individually.

**Best cases.** Two empty-mask images (0128, 0483) are correctly predicted
empty (Dice 1.0). The best wound images score 0.98–0.99 (0796, 0901, 0375,
0745). One of them, 0375, belongs to the same-wound group as the quarantined
train images 0023 and 0200. This is a concrete example of the patient-overlap
optimism described above. Figures: `reports/figures/spec-02-03/heldout_test_worst.png` and
`heldout_test_best.png`. These were regenerated so the drawn prediction
includes the small-component removal that was scored. The Kaggle-run copies
draw the pre-removal mask.

## 5. External check — LowerLimbFeetWound V3 (2,685 images, no tuning)

| Subset | n | Macro Dice | Notes |
|---|---|---|---|
| All | 2,685 | 0.268 (pooled 0.251) | precision 0.92, recall 0.23 |
| Masks distributed at 224 px | 322 | **0.781** | masks tightly follow the wound |
| Masks at native 331 px | 2,363 | 0.198 | 966 images get an empty prediction |

Observed:
- The model's predictions sit inside the annotated area (precision 0.92) but
  cover much less of it (median predicted area 0.5% vs ground truth 7.4%).
- Visual review of the 331 px subset shows coarse, blocky masks that
  sometimes extend well beyond the visible wound or are offset from it. It
  also shows many non-foot wounds (leg ulcers, surgical wounds).
- On the 224 px subset, where masks are precise, the model transfers well
  (0.78).

Hypothesis: most of the gap comes from a different annotation protocol and
wound population, not only from a failure to generalize. It cannot be
separated without a clean, independent foot-ulcer test set. The headline
external number stays **0.268**. The subset split is reported as analysis, not
as a replacement.

## 6. Independent metric check

The downloaded checkpoint was re-evaluated from scratch on a local CPU
(Python 3.14, PyTorch 2.14.1+cpu, fp32, no AMP): internal-val tuning first,
then the held-out test. Outputs are in
`reports/experiments/spec-02-03/cpu_verification/`.

- **The post-processing selection reproduced exactly:** threshold 0.40, area
  128, internal-val macro Dice 0.88854 (CPU) vs 0.88855 (Kaggle).
- **All 40 numeric aggregate test metrics agree.** For Dice, IoU, precision
  and recall, the largest difference is 2.5e-5:

| Metric | CPU | Kaggle |
|---|---|---|
| Macro Dice | 0.84142 | 0.84141 |
| Pooled Dice | 0.92223 | 0.92223 |
| Non-empty Dice | 0.85328 | 0.85327 |
| Macro IoU | 0.77784 | 0.77783 |
| Empty FP rate | 0.6 | 0.6 |
| HD95 median / mean (px) | 3.284 / 18.523 | 3.284 / 18.519 |

The small differences come from fp16 autocast on the T4 vs fp32 on CPU. They
move a handful of boundary pixels across the threshold. None of them changes
a reported figure at three decimals, except mean HD95 (0.004 px).

## 7. Reproducibility

- Config: `configs/training/segmentation_resnet34_unet_512.json` (resolved copy
  in `experiment_record.json`).
- Manifests: `fuseg2021-heldout-v1` and `lowerlimb-v3-external-v1`.
- Launch: `python scripts/launch_kaggle_spec_02_03.py --username <user> --all`.
- Seed 42 with `deterministic=false` (cuDNN autotune + AMP). Reruns agree
  closely but not bit-for-bit.
- Resume: the latest-checkpoint resume path is verified by the CPU
  train-and-resume unit test (`tests/unit/test_spec_02_03.py`). The Kaggle run
  was not interrupted, so it was not exercised there.
- Technical segmentation metrics do not establish clinical efficacy.
