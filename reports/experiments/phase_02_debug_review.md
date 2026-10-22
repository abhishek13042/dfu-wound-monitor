# Phase 02 Historical Demo Debug & Review — Validation Audit Report

> **SUPERSEDED (2026-10-21).** This audit covers only the historical synthetic
> demo (`P02-DEMO-SYNTHETIC-LEAKED`). Its gate statement in section 8, that
> the phase is blocked "until verified real DFUC2022 data is supplied", is
> obsolete:
>
> - DFUC2022 is license-blocked.
> - The real-data baseline uses FUSeg2021 (SPEC-02-01 / SPEC-02-02).
> - The files `P02-baseline-unet-bce-dice-v1_experiment_record.json` and
>   `_training_log.json` belong to this synthetic run. They are not real-data
>   evidence.

**Project:** DFU-WoundMonitor  
**Repository:** `dfu-wound-monitor`  
**Audit Target:** Historical synthetic Phase 02 demo only
**Audit Date:** 2026-10-07  
**Auditor:** Lead AI/CV Engineering Auditor  

---

## 1. Audit Summary

An independent validation audit of the historical synthetic demonstration was conducted. The reported metrics ($\text{Mean Dice} = 1.0000$, $\text{Mean IoU} = 1.0000$) were audited for data leakage, mathematical accuracy, pipeline integrity, and scientific validity. This document is historical evidence, not a real-data baseline report.

### Key Audit Finding
The perfect score ($\text{Dice} = 1.0000$) is **code-correct and reproducible**, but is a direct consequence of **checksum leakage in the Phase 01 demo synthetic dataset**, where all 20 images in the demo manifest are bit-for-bit identical files. As a result, the test set images are identical to the training set images.

---

## 2. Dataset Split Verification

- **Manifest:** `data/manifests/dataset_manifest.json`
- **Split Distribution:** Train: 14 samples, Validation: 3 samples, Test: 3 samples (Total: 20).
- **Patient Isolation:** Patient IDs are absent (`null`) in the public demo release (`patient_level_isolation_achieved: false`).
- **Checksum Overlap Audit:**
  - `SHA256` checksum for ALL 20 sample images: `5ba23a8923901235da470fce7bcf18ccbbc6bd4f0086169cb9e58e2281f89006`.
  - **Train vs Val Overlap:** 42 pairwise duplicate overlaps (100% duplicate file content).
  - **Train vs Test Overlap:** 42 pairwise duplicate overlaps (100% duplicate file content).
  - **Val vs Test Overlap:** 9 pairwise duplicate overlaps (100% duplicate file content).

*Conclusion:* The dataset split logic in code preserves manifest split labels, but the underlying demo dataset contains identical files across splits.

---

## 3. Test Set Analysis

| Sample ID | Image Dims | Mask Dims | Unique Mask Values | FG Pixels | FG % | Bounding Box [xmin, ymin, xmax, ymax] | Empty Mask |
|---|---|---|---|---|---|---|---|
| `DFUC22_0009` | 512 × 512 | 512 × 512 | `{0, 255}` | 40,000 | 15.26% | `[150, 150, 349, 349]` | False |
| `DFUC22_0001` | 512 × 512 | 512 × 512 | `{0, 255}` | 40,000 | 15.26% | `[150, 150, 349, 349]` | False |
| `DFUC22_0004` | 512 × 512 | 512 × 512 | `{0, 255}` | 40,000 | 15.26% | `[150, 150, 349, 349]` | False |

*Observation:* All 3 test set samples are synthetic images with identical centered square foreground lesion masks.

---

## 4. Data Loader Verification

- **Image Loading:** PIL RGB conversion $\to$ Bilinear resize ($256 \times 256$) $\to$ ImageNet normalization (`mean=[0.485, 0.456, 0.406]`, `std=[0.229, 0.224, 0.225]`).
- **Mask Loading:** PIL Grayscale `L` mode $\to$ Nearest Neighbor resize ($256 \times 256$) $\to$ threshold at 128 $\to$ strict binary $\{0.0, 1.0\}$.
- **Spatial Alignment:** Nearest neighbor interpolation preserves crisp binary boundary without intermediate gray artifacts.
- **Leakage Check:** Image and mask loading are fully decoupled; no mask information enters the image tensor.

---

## 5. Preprocessing & Augmentation Verification

- **Train Augmentation:** Horizontal flip ($p=0.5$) applied synchronously to both image and mask tensors (`torch.flip(dim=2)`).
- **Val/Test Preprocessing:** Strictly deterministic, zero random augmentation applied.

---

## 6. Model Verification

- **Architecture:** 4-level U-Net (`LightweightUNet`) with skip connections.
- **Parameters:** 3,350,273 trainable parameters.
- **Tensor Shapes:** Input $(B, 3, 256, 256) \to$ Output $(B, 1, 256, 256)$.
- **Output Range:** Probabilities in $[0.0, 1.0]$ via `torch.sigmoid`.
- **Target Leakage:** None found in model code.

---

## 7. Loss Function Verification

- **Formulation:** $\mathcal{L} = 0.5 \cdot \text{BCE} + 0.5 \cdot \text{Dice}$.
- **Synthetic Test Comparison:**
  - Computed PyTorch Loss: `0.123066`
  - Manual Derivation: `0.123066`
  - **Difference:** `0.000000` (Exact mathematical agreement).

---

## 8. Metric Implementation Verification

- **Formulate Definitions:**
  - $\text{Dice} = \frac{2 \text{TP}}{2 \text{TP} + \text{FP} + \text{FN}}$
  - $\text{IoU} = \frac{\text{TP}}{\text{TP} + \text{FP} + \text{FN}}$
  - $\text{Precision} = \frac{\text{TP}}{\text{TP} + \text{FP}}$
  - $\text{Recall} = \frac{\text{TP}}{\text{TP} + \text{FN}}$
- **Binarization Threshold:** $p \ge 0.5$.
- **Aggregation:** Macro-average across test samples.

---

## 9. Independent Metric Calculation

An independent evaluation script verified the exact numbers:
- **Sample `DFUC22_0009`:** $\text{TP}=10,000, \text{FP}=0, \text{FN}=0 \implies \text{Dice}=1.0000, \text{IoU}=1.0000$
- **Sample `DFUC22_0001`:** $\text{TP}=10,000, \text{FP}=0, \text{FN}=0 \implies \text{Dice}=1.0000, \text{IoU}=1.0000$
- **Sample `DFUC22_0004`:** $\text{TP}=10,000, \text{FP}=0, \text{FN}=0 \implies \text{Dice}=1.0000, \text{IoU}=1.0000$
- **Macro Average:** $\text{Dice}=1.0000, \text{IoU}=1.0000, \text{Precision}=1.0000, \text{Recall}=1.0000$.

---

## 10. Prediction vs Ground Truth Analysis

In all 3 test images, the predicted binary mask overlaps ground truth pixel-for-pixel:
- GT Foreground Pixels: 10,000
- Predicted Foreground Pixels: 10,000
- True Positives: 10,000
- False Positives: 0
- False Negatives: 0

---

## 11. Mask Leakage Audit

- Mask path used as image path: **NO**
- Target concatenated into input: **NO**
- Target leaked into model forward pass: **NO**
- Evaluator comparing mask with itself: **NO**

---

## 12. Checkpoint Audit

- **File:** `models/checkpoints/P02-baseline-unet-bce-dice-v1_best_val_dice.pth`
- **Saved Epoch:** 10
- **Validation Metric:** Val Dice = 1.0000
- **Integrity:** Valid PyTorch model state dict, fully compatible with `LightweightUNet`.

---

## 13. Training Loop Audit

- Order verified: `model.train()`, `optimizer.zero_grad()`, `loss.backward()`, `optimizer.step()`.
- Validation order: `model.eval()`, `torch.no_grad()`.

---

## 14. Qualitative Review

Visualizations generated under `outputs/visualizations/phase_02_qualitative/` confirm 100% overlay alignment for all 3 test images. Classified as **GOOD** (3/3).

---

## 15. Reproducibility Check

- **Run 1 Test Dice:** 1.0000
- **Run 2 Test Dice:** 1.0000
- **Difference:** 0.0000 (100% reproducible).

---

## 16. Unit Test Results

Executed command:
```bash
python -m pytest tests/unit/ -v
```
**Result:** **42 / 42 PASSED** (3.61s).

---

## 17. Historical Spec Traceability Review

- The original audit recorded all 54 requirements as **PASS / COMPLETED**.
- That historical claim is superseded by the reconciled matrix in
  `specs/TRACEABILITY.md`, which distinguishes code-level evidence from the
  blocked real-data gate.

---

## 18. Bugs Found

- **Zero code implementation bugs found** in `src/segmentation/`.
- **Data anomaly noted:** Phase 01 demo dataset generator created 20 duplicate synthetic images, causing cross-split data overlap in the demo environment.

---

## 19. Corrections Made

None required in Phase 02 code modules.

---

## 20. Final Scientific Interpretation

> [!IMPORTANT]
> **Scientific Interpretation:**  
> The statement *"The baseline model achieved Dice = 1.0000"* is mathematically true for this run on the demo dataset. However, because all test samples are duplicate copies of the training set samples, **this score MUST NOT be interpreted as evidence of real-world generalization or clinical efficacy**. Full clinical evaluation requires scaling up to diverse, multi-center datasets (DFUC2022 full benchmark).

---

## 21. Phase 02 Gate Recommendation

**Historical demo status:** **PRESERVED — NOT VALID FOR GENERALIZATION**
- The implementation audit findings are retained.
- The synthetic demo contains cross-split checksum leakage.
- The project Phase 02 gate remains `IMPLEMENTATION COMPLETE / REAL-DATA VALIDATION BLOCKED` until verified real DFUC2022 data is supplied.

---

## Audit Status Summary Block

```
PHASE 02 HISTORICAL DEMO DEBUG STATUS: PRESERVED / LEAKAGE-CONTAMINATED
PERFECT SCORE STATUS: VERIFIED (ON DEMO DUPLICATE DATASET)
DATA LEAKAGE: FOUND (CHECKSUM LEAKAGE IN DEMO DATASET GENERATION)
METRIC IMPLEMENTATION: CORRECT
CHECKPOINT: VERIFIED
REPRODUCIBILITY: PASS
UNIT TESTS: 42 / 42 PASSED
BUGS FOUND: 0 (CODE), 1 (DEMO DATA DUPLICATION)
BUGS FIXED: 0
SCIENTIFIC LIMITATION: Perfect score is due to duplicate synthetic demo samples across splits; does not indicate clinical generalization.
REAL-DATA PHASE 02: BLOCKED (DATASET NOT AVAILABLE LOCALLY)
```
