# SPEC-02-01 Baseline Decision Record

**Project:** DFU-WoundMonitor  
**Specification:** SPEC-02-01 — Baseline Segmentation Pipeline  
**Date:** 2026-10-08  
**Status:** ACCEPTED AND IMPLEMENTED ON REAL FUSeg2021 DATA

## Problem and clinical boundary

Establish a reproducible binary wound-segmentation reference for image-derived
monitoring. The system is a research prototype and does not diagnose, make
treatment recommendations, or establish clinical validity.

## Dataset evidence

FUSeg2021 is the primary and only dataset used by SPEC-02-01. The verified
source is the official FUSeg challenge/UWM repository snapshot recorded in
`configs/data/fuseg2021.json` and `data/manifests/dataset_manifest.json`.

| Contract item | Verified value |
|---|---|
| Official source split | 810 train, 200 validation, 200 public test images |
| Labeled training data | 793 usable train samples after exact duplicate-image quarantine |
| Labeled validation data | 191 usable validation samples after duplicate/invalid-mask quarantine |
| Public test data | 200 images, no usable public ground-truth masks |
| Image format/shape | RGB PNG, 512 × 512 |
| Mask contract | Grayscale binary values `{0,255}`; one validation mask containing `32` was excluded |
| Patient/examination IDs | Not available; no identifiers were inferred |
| Split policy | Official train/validation/test assignments preserved; no re-split |
| Leakage result | PASS after exact duplicate image quarantine; repeated empty-mask checksum is explicitly allowed |

Empty masks are valid FUSeg annotations and remain in the supervised data. Raw
files are unchanged. All exclusions and quality observations are recorded in
`data/manifests/fuseg2021_quality_report.json`.

## Task selection

Binary wound segmentation is directly supported by the released pixel masks and
produces the boundary representation needed by later measurement work.
Detection/localization was not selected because validated bounding boxes are not
provided and deriving them would add an unvalidated annotation conversion.

## Model selection

The selected model is an explicit lightweight four-level U-Net. A U-Net was
preferred to a simple fully convolutional classifier because skip connections
retain boundary detail while remaining understandable and CPU-runnable. It is
materially simpler than later pretrained or attention-based models.

### Architecture contract

- Input: `(B, 3, H, W)` normalized RGB tensor; SPEC-02-01 run uses `256 × 256`.
- Encoder: four `DoubleConvBlock` levels with channels `[16, 32, 64, 128]`, each followed by `2 × 2` max pooling.
- Bottleneck: `DoubleConvBlock` at 128 channels.
- Decoder: four bilinear interpolation + skip concatenation + `DoubleConvBlock` levels.
- Output: `1 × 1` convolution producing `(B, 1, H, W)` raw logits.
- Activations: ReLU in convolution blocks; sigmoid is applied only for Dice/metrics/inference.
- Initialization: Kaiming-normal convolution weights; BatchNorm weights one and biases zero.
- Pretrained weights: none.
- Parameter count: recorded in the run model metadata artifact.

## Loss selection

The final loss is `0.5 * BCEWithLogitsLoss + 0.5 * soft Dice loss`. Raw logits
are passed to `BCEWithLogitsLoss` for numerical stability. Dice uses sigmoid
probabilities, computes a per-image score, averages over the batch, and uses an
epsilon for empty-mask stability. Targets are validated to be in `[0,1]`.

## Preprocessing and augmentation

- Decode with PIL and fail clearly on unreadable files.
- Convert images to RGB.
- Resize images bilinearly and masks with nearest-neighbor interpolation to configurable `H × W`.
- Normalize RGB values with mean `[0.485, 0.456, 0.406]` and standard deviation `[0.229, 0.224, 0.225]`.
- Threshold masks at 128 to strict `{0,1}` tensors.
- Apply deterministic, seeded horizontal flips only to training image/mask pairs.
- Validation preprocessing is deterministic and has no random augmentation.

## Training and selection

The run configuration is `configs/training/baseline_segmentation_real.json`.
Adam, the configured learning rate/weight decay, deterministic seed controls,
optional scheduler, CPU fallback, per-epoch train/validation logging, and
maximum validation Dice checkpoint selection are all configuration-controlled.
The public unlabeled test split is never passed to the training loop.

## Historical separation and later scope

The former synthetic DFUC2022 smoke experiment remains historical and is not
used as real-data evidence. Complete labeled test evaluation, independent test
metric verification, and later improvements belong to SPEC-02-02 or later and
are not started by this specification.
