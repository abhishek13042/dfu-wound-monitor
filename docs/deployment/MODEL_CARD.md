---
tags:
- image-segmentation
- medical-imaging
- research-prototype
library_name: pytorch
datasets:
- FUSeg2021
metrics:
- dice
---

# DFU ResNet34 U-Net (spec-02-03-resnet34-unet-512-v1)

> Research artifact. Not a medical device, not clinically validated, and not for diagnosis or treatment decisions.

A binary segmentation model for foot-ulcer regions in photographs. It is a U-Net decoder on an ImageNet-initialised
ResNet34 encoder, trained at 512 × 512 on FUSeg2021. The weights are the EMA weights from epoch 71.

| Item | Value |
|---|---|
| File | `resnet34_unet_512_best.pth` (dict with `model_state_dict`) |
| SHA-256 | `26aca52e401f23b5781d2596d74c1fd7fa86a6af0ab9fb3db9fa17dcffb5cf04` |
| Inference contract | sigmoid, threshold **0.40**, components below **128 px** removed, horizontal-flip TTA |
| Preprocessing | taken from the training config `configs/training/segmentation_resnet34_unet_512.json` |

Post-processing was frozen on internal validation **before** the held-out test was scored.

## Results

| Evaluation | n | Pooled Dice | Macro Dice |
|---|---|---|---|
| FUSeg2021 held-out test | 191 | 0.922 | 0.841 |
| End-to-end service rerun (P06) | 191 | 0.922 | 0.841 (max per-image difference vs. Phase 02: 0.0003) |

Of the 191 test images, 156 are well segmented. The rest are 8 missed wounds, 10 under-segmented,
6 over-segmented, 6 with low overlap and 3 false positives on empty images. External LowerLimb images show a
measurable drop in accuracy. The full validation report is in the project repository at
`reports/final/phase_06_validation_report.md`.

## Limitations

- Trained only on FUSeg2021. Behaviour on other cameras, skin tones, wound types or protocols has not been established.
- Area and perimeter are pixel values unless a `pixels_per_mm` calibration is supplied.
- Use it with the project's inference engine, which verifies this hash and applies the contract above.
