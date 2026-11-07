# P09-S04 protocol: the annotation-protocol hypothesis

Frozen on 2026-11-05, before `scripts/evaluation/run_annotation_hypothesis.py` was first run. Changes after that date are listed at the end, with their reasons; none may change a test or a threshold below.

## What is already known

These came from P06, before this protocol was written. They are why the hypothesis exists, so they cannot also be the test of it.

- On 148 accepted LowerLimb V3 images, pooled Dice is 0.256. Precision is 0.90 and recall 0.15 (`reports/final/p06_validation_lowerlimb_external.json`).
- The 16 images whose masks were shipped at 224 × 224 score a mean Dice of 0.816. The 132 with native 331 × 331 masks score 0.195 (`reports/final/p06_lowerlimb_annotation_check.json`).
- In 12 probed images, the model's probability in the labelled-but-missed region is near zero. A lower threshold would not recover it.

## Hypothesis

**H1:** the drop on native-331 masks is mainly a difference in what was labelled. Those masks cover a wider region than the FUSeg2021 style, such as the skin around the wound, so the model's narrower answer is scored as a miss.

**H0:** the labelled-but-missed region is wound that the model fails to see.

## Data

- The same 148 accepted external images as P06, split by mask form: native_331 and resized_224. They are reported as separate strata, never as one mixed score.
- The 191 FUSeg2021 held-out test masks, for the shape comparison only.
- These images have been seen. This study explains a result; it is not a new external test (REQ-P09-S04-002).
- No model is trained or tuned. The frozen v1.0.0 model and threshold are used, with the inference config `configs/inference/spec_02_03_inference.json`.

## Tests, fixed in advance

**T1, colour of the missed region.**
- Take each native_331 image where the hit region (predicted and labelled), the missed region (labelled, not predicted) and the surrounding ring each have at least 50 pixels.
- The ring is the band from 5 to 15 pixels outside the label.
- Compute the mean CIELAB colour of each region.
- The missed region counts as skin-like when its colour distance (ΔE76) to the ring is smaller than its distance to the hit region.
- **T1 supports H1** when at least 60 % of eligible images are skin-like.
- The same numbers are reported for resized_224, for comparison only.

**T2, shape of the label.**
- Compute each label's solidity: area ÷ convex-hull area, using the largest connected part.
- **T2 supports H1** when the native_331 median is at least 0.05 above the FUSeg2021 test median. Coarser, outline-style labels are more convex.
- Label area as a share of the image is reported beside it, as a description only.

**Descriptive only, not a test:** the mean model probability inside the missed region for every native_331 image with a missed region. This extends the 12-image probe.

## Decision

| T1 | T2 | Reported outcome |
|---|---|---|
| supports | supports | H1 supported |
| one supports | | H1 partly supported |
| neither | | H1 not supported; H0 stays the working explanation |

The outcome is reported whatever it is (REQ-P09-S04-001). Either way, the v1.0.0 external result of 0.256 stays published (REQ-P09-S04-004).

## What each outcome would lead to

- **Supported:** retraining will not fix a labelling difference. The next step is a new external set with FUSeg-style labels, or relabelling a sample of LowerLimb images to that style, fixed before any training.
- **Not supported:** combined-source training and appearance augmentation are justified. They need GPU time that this machine does not have.

## Limits declared in advance

- Colour is a proxy. Skin-like colour does not prove a region is not wound: slough and epithelialising edges can look like skin.
- The 148 images were sampled from 2,685 in P06; this study does not draw a new sample.
- There is no patient grouping in LowerLimb V3, so near-duplicate images of one patient may sit in the same stratum.

## Changes after freezing

None.
