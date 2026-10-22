# Phase 06 validation report (P06-S01, P06-S02)

> Research prototype. These are technical segmentation and measurement results, not clinical performance.

| Item | Value |
|---|---|
| Model | `spec-02-03-resnet34-unet-512-v1`, SHA-256 `26aca52e…cf04`, verified before each run |
| Inference contract | `configs/inference/spec_02_03_inference.json` (threshold 0.40, min area 128 px, flip TTA) |
| Path under test | the full service pipeline: decode → quality gate → segmentation → measurement |
| Raw results | `reports/final/p06_validation_fuseg2021_test.json`, `p06_validation_lowerlimb_external.json`, `p06_lowerlimb_annotation_check.json`, `p06_benchmark.json` |
| Figures | `reports/figures/p06/*_dice_and_area.png` (example image sheets are kept local, because dataset redistribution terms are not recorded) |
| Commands | `python scripts/evaluation/run_phase_06_validation.py --split test --tag fuseg2021_test`, `... --manifest data/manifests/lowerlimb_v3_external_manifest.json --split external_test --limit 150 --tag lowerlimb_external`, `python scripts/evaluation/inspect_lowerlimb_annotations.py`, `python scripts/evaluation/run_phase_06_benchmark.py --images 20` |

## 1. FUSeg2021 held-out test (in-domain, 191 images)

| Metric | Value |
|---|---|
| Quality gate | 191 / 191 accepted |
| Pooled Dice / IoU | **0.922** / 0.856 |
| Macro per-image Dice | **0.841** (std 0.243); median 0.932, p10 0.677, p90 0.977 |
| Macro Dice, images with a non-empty mask (186) | 0.853 |
| Agreement with Phase 02 evaluation | 191 compared; max per-image Dice difference 0.00029; none > 0.01 |
| Repeatability | 5 / 5 images give a bit-identical mask and probability map on rerun |

**Dice by ground-truth wound size (terciles):**

| Size | Area (px) | n | Mean Dice | Median Dice |
|---|---|---|---|---|
| Small | < 1,032 | 62 | 0.744 | 0.907 |
| Medium | 1,032 – 2,948 | 62 | 0.882 | 0.921 |
| Large | ≥ 2,948 | 62 | 0.934 | 0.957 |

Small wounds carry almost all of the variance: their p10 Dice is 0.0, compared with 0.88 for large wounds.

**Measurement error** (178 images where both the mask and prediction are non-empty; relative to the ground-truth mask):

| Quantity | Median | p10 – p90 |
|---|---|---|
| Area, relative error | +0.018 | −0.174 to +0.263 |
| Area, absolute relative error | 0.076 | 0.011 to 0.399 |
| Max Feret diameter, relative error | 0.000 | −0.240 to +0.178 |

Five images have an area error above +100%. All five are small wounds, with true areas of 43–1,005 px. In each, the prediction is 3–9× too large. In four of them it is a single oversized region; one is fragmented. When the true area is this small, a modest boundary offset becomes a large relative error.

### Observed error categories (rule-based; rules are stored in the JSON)

| Category | Count | Rule |
|---|---|---|
| GOOD | 156 | Dice ≥ 0.8 |
| UNDER_SEGMENTATION | 10 | 0.5 ≤ Dice < 0.8, predicted area < true area |
| OVER_SEGMENTATION | 6 | 0.5 ≤ Dice < 0.8, predicted area ≥ true area |
| LOW_OVERLAP | 6 | both non-empty, Dice < 0.5 |
| MISSED_WOUND | 8 | wound present, prediction empty |
| FALSE_POSITIVE_ON_EMPTY | 3 | no wound, region predicted |
| CORRECT_EMPTY | 2 | no wound, nothing predicted |

Flags: 73 images are `SMALL_WOUND` (under 0.5% of the image) and 11 are `FRAGMENTED_PREDICTION`.

### Hypotheses (not established)

- *H1:* missed wounds are mostly small wounds with low contrast to the surrounding skin. This is consistent with the size-tercile table, but contrast was not measured.

## 2. LowerLimbFeetWound V3 (external, 150 evenly spaced images)

| Metric | Value |
|---|---|
| Quality gate | 148 / 150 accepted (2 `BLURRY`) |
| Pooled Dice / IoU | **0.256** / 0.147 |
| Macro per-image Dice | **0.262** (median 0.149, p90 0.821) |
| Precision / recall (median per image) | **0.968 / 0.080** |
| Pooled precision / recall | 0.903 / 0.149 |
| Area relative error (97 with both masks non-empty) | median **−0.785** |
| Repeatability | 5 / 5 bit-identical |

Category counts: GOOD 18, UNDER_SEGMENTATION 13, OVER_SEGMENTATION 2, LOW_OVERLAP 64, MISSED_WOUND 51, QUALITY_REJECTED 2.

This is a large drop from in-domain performance. The model rarely marks a region that is not labelled. Its main error is covering far less than the labelled region.

### Observed: the drop is concentrated in one of two annotation forms

LowerLimb V3 provides masks in two forms. In the full dataset, 322 masks are 224 × 224 and are nearest-resized to the image size. The other 2,364 masks are native 331 × 331.

| Mask form | n | Mean Dice | Median Dice | Median recall | Median labelled area (share of image) |
|---|---|---|---|---|---|
| Resized 224 | 16 | **0.816** | 0.888 | 0.943 | 3.0% |
| Native 331 | 132 | **0.195** | 0.074 | 0.039 | 7.7% |

Both groups are equally distant from FUSeg2021 by perceptual hash: median Hamming distance 20, minimum 16. The good score on the 224 group therefore does not come from near-duplicates of training images.

**Probability probe** (`p06_lowerlimb_annotation_check.json`, 6 images per form): this measures the model's confidence inside the labelled region that it did not mark.
- For native-331 masks, the mean probability there is 0.00–0.07, and at most 17% of those pixels exceed 0.2.
- For resized-224 masks, the missed regions are small (6–1,537 px) with mean probability 0.04–0.31. They are boundary pixels.

Any threshold change near 0.40 therefore would not recover the native-331 regions: the model assigns them near-zero probability.

**Visual review** of 12 images (image, label, prediction):
- The resized-224 labels trace the wound edge, in the same style as FUSeg2021, and the predictions match them.
- Native-331 labels are visibly blocky.
- In several native-331 images the label does not line up with the visible wound:
  - 0037: the label is offset from two small wounds that the model marks.
  - 0506: the label covers callused forefoot skin; nothing is predicted.
  - 1893: the label is much larger than the visible wound.
  - 2290: the label is a large block around a pinpoint lesion.
- At least one native-331 image (1389) shows a visible lesion that is labelled and that the model misses entirely.

### Hypotheses (not established)

- *H2:* most of the external drop comes from a difference in annotation protocol, not from model failure. The native-331 labels seem to mark a coarser and broader region, sometimes misaligned, than the wound-bed protocol of FUSeg2021. Evidence for H2: the gap between the two mask forms (0.82 vs 0.20), the high precision with low recall, and the visual review. It is not established, because only 16 images have the resized-224 form and only 12 images were reviewed.
- *H3:* part of the drop is real domain shift: lower-leg wounds, different cameras, and blurrier images. Image 1389 is a clear model miss on a correctly placed label.
- Telling H2 from H3 would need a re-annotation of a native-331 subset with the FUSeg protocol. Until then, **0.26 is reported as the external result**. It is not adjusted, and no subset is presented as the headline.

## 3. Reliability and performance (P06-S02)

Hardware: Intel CPU with 2 physical / 4 logical cores at 2.9 GHz, 7.7 GB RAM, Windows 11, torch 2.14.1+cpu with 2 threads, no GPU.
Input: 20 FUSeg test images (512 × 512) after 2 warm-up runs.

| Stage | Mean (s) | p50 | p90 |
|---|---|---|---|
| Decode | 0.009 | 0.010 | 0.011 |
| Quality gate | 0.090 | 0.092 | 0.108 |
| Segmentation (with TTA) | 5.572 | 5.563 | 5.967 |
| Measurement | 0.084 | 0.076 | 0.123 |
| **Total pipeline** | **5.756** | 5.776 | 6.141 |
| API end-to-end (5 uploads) | 5.316 | 5.427 | 5.638 |

- **Bottleneck:** segmentation takes 96.8% of total time. Without TTA it takes 1.34 s (p50), a 4.1× difference, which is more than the 2× expected from two forward passes. The cause was not profiled.
- **Model load (cold start):** 2.5 s after hashing.
- **Memory:** about 330 MB RSS before loading and about 655 MB after loading, with a peak working set of 914 MB.
- **Repeatability:** 5 runs of one image give 1 distinct mask/probability hash.
- **Boundary inputs** each map to their own failure class, and the service stays READY afterwards:

| Input | HTTP status | Failure class | Code |
|---|---|---|---|
| Empty payload | 400 | INPUT | INPUT_MISSING |
| Truncated PNG | 400 | INPUT | INPUT_UNREADABLE |
| Text file | 400 | INPUT | INPUT_UNREADABLE |
| GIF | 400 | INPUT | INPUT_UNREADABLE |
| Oversize upload | 413 | INPUT | INPUT_TOO_LARGE |
| 32 px image | 422 | QUALITY | QUALITY_REJECTED |
| Extreme aspect ratio (2000 × 100) | 422 | QUALITY | QUALITY_REJECTED |
| Uniform grey | 422 | QUALITY | QUALITY_REJECTED |

- **Optimisation decision:** none applied. No latency requirement exists, so REQ-P06-S02-004's precondition (a bottleneck that violates a stated requirement) is not met. If one is set, the first candidates are dropping TTA (measured above) or ONNX export.

## 4. Conclusions

1. In-domain, the shipped service reproduces the Phase 02 held-out result exactly (pooled Dice 0.922). Errors concentrate in small wounds.
2. Externally, the score drops to Dice 0.26. The evidence points largely to annotation-protocol disagreement on the native-331 LowerLimb masks (H2), with some real misses (H3). Generalisation beyond FUSeg2021 is **not** established.
3. Area measurements follow segmentation quality: median error is +1.8% in-domain and −79% on the native-331 external labels. Any use of area values inherits the segmentation limitations above.
4. On a 2-core laptop CPU, one analysis takes about 5.8 s, almost all of it in the segmentation model.
