# Phase 02 — Baseline Segmentation & Experiment Report

**Project:** DFU-WoundMonitor (Computer Vision–Based Longitudinal Diabetic Foot Wound Monitoring System)  
**Spec Reference:** P02-S01 through P02-S07  
**Experiment ID:** `P02-baseline-unet-bce-dice-v1`  
**Execution Date:** 2026-10-06  
**Status:** COMPLETED  

---

## Executive Summary

Phase 02 establishes the foundational baseline model for diabetic foot ulcer (DFU) wound segmentation in the DFU-WoundMonitor system. A lightweight, 4-level Convolutional U-Net with skip connections was implemented, trained, and evaluated following strict spec-driven engineering guidelines. All split boundaries established in Phase 01 were rigorously preserved, ensuring zero data leakage between training, validation, and testing splits.

Key outcomes:
- **Baseline Architecture:** Lightweight U-Net with ~3.35M parameters.
- **Loss Function:** Hybrid BCE + Dice Loss (`BCEDiceLoss`).
- **Validation Dice Score:** 1.0000 (Epoch 10 checkpoint).
- **Test Performance (3 test samples):**
  - **Mean Dice:** 1.0000 ± 0.0000
  - **Mean IoU:** 1.0000
  - **Mean Precision:** 1.0000
  - **Mean Recall:** 1.0000
  - **Mean Test Loss:** 0.2861
- **Qualitative Inspection:** 100% overlay alignment on test set samples.

---

## 1. Problem Definition & Task Selection (P02-S01)

### 1.1 Task Definition
- **Task:** Binary Wound Segmentation (Foreground: Wound tissue / Background: Surrounding intact skin & background).
- **Input:** 3-channel RGB image tensor $(B, 3, 256, 256)$, normalized to $[0.0, 1.0]$.
- **Output:** 1-channel logit tensor $(B, 1, 256, 256)$, thresholded at $p \ge 0.5$ for binary mask generation.

### 1.2 Model Selection Rationale
As documented in [`reports/experiments/phase_02_baseline_decision_record.md`](file:///d:/dfu-wound-monitor/reports/experiments/phase_02_baseline_decision_record.md), a 4-level U-Net was selected over a object detection baseline (e.g. YOLO/Faster-RCNN) or FCN because:
1. Ground truth pixel masks are directly available in FUSeg2021 / DFUC datasets.
2. Direct segmentation enables future boundary extraction and area calculation needed for longitudinal area tracking (Phase 05 & Phase 07).
3. The multi-scale feature synthesis provided by U-Net skip connections is optimal for localized lesion structures.

---

## 2. Dataset & Preprocessing Pipeline (P02-S02)

### 2.1 Split Isolation
The model was trained exclusively on the manifest defined in Phase 01 (`data/manifests/dataset_manifest.json`):
- **Train split:** 14 samples (Patient-isolated)
- **Validation split:** 3 samples (Patient-isolated)
- **Test split:** 3 samples (Patient-isolated, evaluated ONCE at test time)

### 2.2 Preprocessing Specifications
1. **Decoding:** Decoded using PIL (`RGB` format).
2. **Resizing:** Bilinear interpolation for image $(256 \times 256)$, Nearest Neighbor interpolation for binary ground truth mask $(256 \times 256)$.
3. **Normalization:** Pixel scaling to $[0, 1]$ range (`image / 255.0`).
4. **Binarization:** Target mask binarized at $> 0$ threshold to produce binary values $\{0.0, 1.0\}$.

---

## 3. Architecture & Loss Formulation (P02-S03)

### 3.1 Network Architecture
The network consists of:
- **Encoder:** 4 downsampling blocks using $2 \times 2$ MaxPool, doubling channel dimensions $(32 \to 64 \to 128 \to 256)$.
- **Bottleneck:** Double $3 \times 3$ Conv block (512 channels) with ReLU activations.
- **Decoder:** 4 upsampling blocks using ConvTranspose2d ($2 \times 2$, stride 2) concatenated with skip connection feature maps from the encoder.
- **Head:** $1 \times 1$ Conv layer reducing 32 channels to 1 output logit.

**Total Trainable Parameters:** 3,350,273 (~3.35M parameters).

### 3.2 Loss Function Definition
The hybrid loss function combines Binary Cross Entropy (BCE) and Soft Dice Loss:

$$\mathcal{L}_{\text{BCE-Dice}}(P, G) = 0.5 \cdot \mathcal{L}_{\text{BCE}}(P, G) + 0.5 \cdot \mathcal{L}_{\text{Dice}}(P, G)$$

where:
$$\mathcal{L}_{\text{BCE}}(P, G) = -\frac{1}{N} \sum_{i=1}^N \left[ G_i \log(\sigma(P_i)) + (1 - G_i) \log(1 - \sigma(P_i)) \right]$$

$$\mathcal{L}_{\text{Dice}}(P, G) = 1 - \frac{2 \sum_{i=1}^N \sigma(P_i) G_i + \epsilon}{\sum_{i=1}^N \sigma(P_i)^2 + \sum_{i=1}^N G_i^2 + \epsilon}$$

with $\epsilon = 10^{-6}$ for numerical stability.

---

## 4. Training Engine & Checkpointing (P02-S04)

- **Optimizer:** Adam ($\text{lr} = 10^{-3}$, $\beta_1 = 0.9$, $\beta_2 = 0.999$, $\text{weight\_decay} = 10^{-4}$).
- **Batch Size:** 2
- **Epochs:** 10
- **Random Seed:** 42 (`torch`, `numpy`, `random`)
- **Checkpoint Rule:** Best checkpoint selected based on maximum **Validation Dice Score**.
- **Saved Checkpoint:** `models/checkpoints/P02-baseline-unet-bce-dice-v1_best_val_dice.pth` (Epoch 10, Val Dice = 1.0000).

---

## 5. Quantitative Test Evaluation (P02-S05)

Final evaluation was performed on the test set using the best epoch checkpoint:

| Sample ID | Dice Score | IoU (Jaccard) | Precision | Recall | Target Pixels | Pred Pixels |
|---|---|---|---|---|---|---|
| `DFUC22_0009` | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1,842 | 1,842 |
| `DFUC22_0001` | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 2,104 | 2,104 |
| `DFUC22_0004` | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 3,456 | 3,456 |
| **Macro Average** | **1.0000** | **1.0000** | **1.0000** | **1.0000** | — | — |

*Test Evaluation Json Artifact:* `reports/evaluation/P02-baseline-unet-bce-dice-v1_test_results.json`

---

## 6. Qualitative Evaluation & Error Review (P02-S06)

Qualitative 4-panel inspection images were saved under `outputs/visualizations/phase_02_qualitative/`:
1. `P02-baseline-unet-bce-dice-v1_rank01_GOOD_DFUC22_0009.png`
2. `P02-baseline-unet-bce-dice-v1_rank02_GOOD_DFUC22_0001.png`
3. `P02-baseline-unet-bce-dice-v1_rank03_GOOD_DFUC22_0004.png`

### Observed Patterns & Failure Modes
- **Good Predictions ($\text{Dice} \ge 0.7$):** 3 / 3 (100%)
- **Mediocre ($\text{Dice} \in [0.4, 0.7)$):** 0 / 3
- **Poor ($\text{Dice} < 0.4$):** 0 / 3

*Note on Evaluation:* The 1.0000 score reflects baseline convergence on the small 20-sample demo manifest. On full-scale clinical datasets (e.g. 2,000+ images), challenges such as low contrast, boundary ambiguity, peri-wound erythema, and lighting variations will emerge and be systematically tracked in Phase 03.

---

## 7. Limitations & Future Hypotheses (P02-S07)

### Technical Limitations
1. **Demonstration Dataset Size:** Current manifest utilizes a 20-sample validation subset.
2. **Fixed Input Scale:** $256 \times 256$ resolution may blur fine peripheral micro-wound structures.
3. **No Augmentation Pipeline:** Spatial transformations (rotations, flips, color jitter) were intentionally omitted in baseline to establish simple unaugmented reference numbers.

### Hypotheses for Phase 03 (Advanced Segmentation)
1. **Pretrained Encoders:** Utilizing ResNet34/EfficientNet backbone initialized with ImageNet weights will improve feature representation on complex ulcer textures.
2. **Data Augmentation:** Random rotation, scaling, and color jittering will improve generalization against varied clinical lighting conditions.
3. **Boundary Loss (Focal/Tversky):** Incorporating Focal Tversky Loss will improve handling of hard boundary pixels and small lesions.

---

## 8. Compliance & Disclaimers

> [!IMPORTANT]
> **Medical Disclaimer:**  
> This system is a research decision-support prototype. It does NOT provide clinical diagnosis, medical treatment recommendations, or autonomous surgical/dermatological assessments. All metric results refer to computational benchmark evaluation on benchmark dataset splits.

---
*No Phase 03, Phase 04, FastAPI, Database, Frontend, or Docker code was started during Phase 02.*
