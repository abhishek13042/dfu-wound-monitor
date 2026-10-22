---
title: DFU WoundMonitor
emoji: 🦶
colorFrom: indigo
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
short_description: Research prototype - foot ulcer segmentation and measurement
---

# DFU-WoundMonitor (research demo)

> Research prototype. Not a medical device, not clinically validated, and not for diagnosis or
> treatment decisions. Outputs are image-derived technical measurements of a segmented region.

Upload a foot-ulcer photograph to see what happens:

1. A **quality gate** checks it and rejects unreadable, blurry, badly exposed or glare-dominated images with reason codes.
2. A **ResNet34 U-Net** (512 px, flip TTA, threshold 0.40) segments the wound region.
3. The **measurement** step reports area, perimeter and shape descriptors: in pixels, or in mm / mm²
   when you supply a `pixels_per_mm` calibration.
4. Results are **stored** per case and examination, so technical trends and pairwise comparisons work
   across visits. Missing or incompatible data is reported as `UNAVAILABLE` and never guessed.

| Held-out FUSeg2021 test (191 images) | Value |
|---|---|
| Pooled Dice | 0.922 |
| Macro per-image Dice | 0.841 |
| Quality-gate acceptance | 191 / 191 |

The dashboard is at `/dashboard/`, the interactive API schema at `/docs`, and readiness at `/health/ready`.
This demo stores uploads in temporary storage that is wiped whenever the Space restarts. Do not upload
identifiable patient images.

The model was trained only on FUSeg2021, and it drops in accuracy on other image sources. See the project repository
for the full validation report, limitations and source code.
