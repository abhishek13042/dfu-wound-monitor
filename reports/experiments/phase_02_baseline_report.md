# SPEC-02-01 — FUSeg2021 Baseline Engineering Report

**Status:** implementation and sanity gate complete; multi-epoch Kaggle training
is intentionally deferred. No final-test metrics are reported.

## Scope

SPEC-02-01 establishes a binary wound-segmentation baseline using only the
verified FUSeg2021 source. The selected model is an explicit four-level,
bilinear-upsampled U-Net with random initialization. The public test images are
not evaluated because the release does not provide usable ground-truth masks.

No SPEC-02-02 or Phase 03 implementation was started.

## Dataset and split contract

The source contract is recorded in `configs/data/fuseg2021.json` and the
manifest is `data/manifests/dataset_manifest.json`.

| Item | Verified value |
|---|---|
| Official split | 810 train / 200 validation / 200 test images |
| Usable supervised train | 793 |
| Usable supervised validation | 191 |
| Public test | 200 images, no usable masks |
| Source resolution | 512 × 512 RGB |
| Source masks | binary `{0,255}`; empty masks are valid |
| Patient/exam identifiers | unavailable; no patient-level claim |
| Leakage gate | PASS after exact duplicate-image quarantine |

The manifest preserves the official source assignments. Exact duplicate images
are quarantined without changing raw files. The one validation mask containing
value `32` is excluded by the manifest rather than silently thresholded.

## Loader, preprocessing, and alignment

`src/segmentation/dataset.py` loads only `VALID` manifest records with
`wound_segmentation` annotations. It verifies file existence, image/mask source
dimensions, declared manifest dimensions, grayscale mask channels, and source
mask values before preprocessing.

The tensor contract is:

- image: `(B, 3, 256, 256)`, `float32`;
- target: `(B, 1, 256, 256)`, `float32` in `{0,1}`;
- model output: `(B, 1, 256, 256)`, raw logits.

Images are decoded with PIL, converted to RGB, resized with bilinear
interpolation, scaled to `[0,1]`, and normalized with the configured mean and
standard deviation. Masks use nearest-neighbor resize and threshold `128`.
Training flips are deterministic per sample/seed/epoch and synchronized between
image and mask. Validation has no random augmentation. An optional
`--data-root` remaps the manifest's recorded source root for Kaggle mounts;
the manifest split assignments are still used unchanged.

## Model and loss

`src/segmentation/model.py` implements the selected U-Net explicitly:

- channels `[16,32,64,128]` for the real configuration;
- `DoubleConvBlock` encoder and decoder blocks;
- max pooling in the encoder;
- bilinear interpolation and skip concatenation in the decoder;
- one-channel output convolution with no output sigmoid;
- Kaiming-normal convolution initialization and standard BatchNorm setup.

The configured model has **838,785 total and trainable parameters**. The loss
is `0.5 * BCEWithLogitsLoss + 0.5 * per-image soft Dice loss`. Raw logits are
used for numerically stable BCE; sigmoid is used only for Dice and metrics.
Finite-value, shape, and target-range checks fail clearly.

## Reproducibility, checkpointing, and logging

Configuration is validated by `src/segmentation/config.py` before data loading.
The trainer records Python, NumPy, PyTorch, CUDA, device, epoch, timing,
learning rate, train metrics, validation metrics, and configuration snapshots.
Validation Dice is the predeclared checkpoint-selection metric.

Each completed epoch writes:

- a validation-selected best checkpoint;
- a separate latest-epoch resume checkpoint;
- model and optimizer state;
- scheduler state when configured;
- configuration and environment metadata;
- Python/NumPy/PyTorch/CUDA RNG states and the training DataLoader generator
  state.

Checkpoint writes are atomic. Resume restores the latest epoch state and RNG
streams, while best-checkpoint selection remains validation-only.

## Verification performed

Using a local Python virtual environment with `requirements.txt` installed
(original run: an ephemeral Linux venv; re-verified on 2026-10-21 on Windows
with Python 3.14):

```text
72 passed in tests/unit
real-data sanity-only run: PASS
```

The real sanity run verified 793/191 manifest-backed train/validation loading,
`(8,3,256,256)` and `(8,1,256,256)` batch shapes, binary masks, deterministic
validation preprocessing, one real-batch finite forward/backward pass, finite
gradients, model output shape, and finite logits-based loss. Evidence is saved
in `reports/experiments/P02-SPEC-02-01-fuseg2021_sanity_checks.json` and the
aligned sample panel under `outputs/visualizations/phase_02_fuseg2021_baseline/`.

No multi-epoch CPU training, final test evaluation, or fabricated performance
metric was produced in this continuation.

## Kaggle command

From the repository root, after the FUSeg2021 data is mounted or copied and the
manifest is available, the clean Kaggle wrapper is:

```bash
python scripts/run_kaggle_spec_02_01.py \
  --data-root "/kaggle/input/fuseg2021/Foot Ulcer Segmentation Challenge" \
  --output-root /kaggle/working/spec-02-01 --sanity-only
```

Use `--train` in place of `--sanity-only` on Kaggle to start the configured
train/validation job. Add
`--resume-checkpoint /kaggle/working/spec-02-01/checkpoints/P02-SPEC-02-01-fuseg2021-unet-bce-dice-v1_latest_epoch.pth`
alongside `--train` to resume an interrupted run. Full training is blocked on
CPU by default. The entrypoint never evaluates the unlabeled public test split.

## Remaining work

SPEC-02-02 may perform the approved next evaluation work, including any
independent evaluation protocol for a labeled/authorized test set and associated
error review. It must use the validation-selected checkpoint and must not treat
the unlabeled FUSeg2021 public test images as ground truth.
