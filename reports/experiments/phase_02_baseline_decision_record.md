# Phase 02 Baseline Decision Record

**Spec:** P02-S01 — Baseline Task and Model Selection  
**Date:** 2026-10-07  
**Status:** ACCEPTED  

---

## 1. Problem Statement

Develop a computer vision baseline for the DFU-WoundMonitor prototype.  
The system monitors diabetic foot ulcers (DFU) over time.  
This phase establishes the first reproducible quantitative reference point.

**Clinical boundary:** This baseline is a monitoring prototype only.  
It does NOT diagnose, treat, or make clinical claims about individual wounds.

---

## 2. Phase 01 Evidence Summary

| Evidence Item | Value |
|---|---|
| Dataset | DFUC2022 |
| Annotation type in manifest | `wound_segmentation` |
| Canonical label in manifest | `wound_tissue` |
| Number of samples | 20 (14 train / 3 val / 3 test) |
| Image resolution | 512 × 512 pixels (all samples) |
| Mask convention | Binary PNG, pixel values {0, 255} |
| Valid samples | 20 / 20 (zero invalid) |
| Wound area ratio (sample DFUC22_0001) | 15.26% of image area |
| Foreground background imbalance | Foreground ≈ 15% → background dominant |
| Patient IDs | Not present in public release (image-level split used) |
| Split mode | IMAGE_LEVEL_FALLBACK (documented limitation) |

**Key observation:** All 20 samples carry `annotation_type = "wound_segmentation"` and binary PNG masks.  
No bounding-box annotations exist in the current manifest.  
Detection/localization would require creating bounding boxes from masks — an extra, unvalidated step.  
Segmentation uses the annotations exactly as validated in Phase 01.

---

## 3. Candidate Task Comparison

| Criterion | Wound Segmentation | Wound Detection (Bounding Box) |
|---|---|---|
| **Data support** | ✅ Binary masks present and verified for all 20 samples | ⚠️ No validated bbox annotations — would need synthetic derivation from masks |
| **Task complexity** | Medium — pixel-level binary classification | Lower output complexity, but requires bbox format conversion |
| **Compute** | Moderate (UNet-scale forward pass on 512×512) | Comparable per-image cost |
| **Interpretability** | ✅ High — pixel mask directly shows wound boundary | Moderate — bounding box only gives rough region |
| **Deployment relevance** | ✅ Pixel mask enables area measurement downstream (Phase 05) | Bbox insufficient for area measurement |
| **Longitudinal monitoring** | ✅ Mask area enables wound progression tracking | Bbox area proxy is unreliable for small wounds |
| **Limitations** | Sensitive to boundary annotation quality; foreground imbalance present | Bbox format not present; would introduce unvalidated assumptions |
| **Alignment with Phase 00 architecture** | ✅ segmentation module is primary MVP component | Detection is secondary; explicitly listed as Phase 04 |

**Decision: Wound Segmentation is the clearly supported task.**

Rationale: All Phase 01 annotations are binary masks. Detection would require converting masks to bounding boxes, introducing an extra, unvalidated step not backed by Phase 01 evidence. Segmentation is also directly required for the downstream measurement and longitudinal modules.

---

## 4. Candidate Architecture Comparison

| Criterion | UNet (Encoder-Decoder with Skip Connections) | FCN-8s (Fully Convolutional Network) |
|---|---|---|
| **Simplicity** | ✅ Well-documented, explicit encoder-decoder layout | Moderate — VGG-based, older design |
| **Complexity vs intent** | ✅ Simpler than Transformer or attention-based models | Comparable |
| **Skip connections** | ✅ Preserve spatial/boundary information — important for wound boundary | ❌ Limited spatial preservation |
| **Output quality** | ✅ Better boundary delineation for small/irregular objects | Coarser predictions |
| **Baseline defensibility** | ✅ UNet is the standard, literature-accepted baseline for medical segmentation | FCN-8s is outdated by modern standards |
| **Compute** | ✅ CPU-runnable at 256×256 or 512×512 with small encoder | Comparable but larger VGG backbone |
| **Literature alignment** | ✅ DFUC2022 leaderboard uses UNet and variants | Less common in recent DFU literature |
| **Understandability** | ✅ Explicit skip connection logic is teachable | More implicit in FCN |

**Decision: UNet with a lightweight encoder (4 levels, no pretrained weights initially) is selected.**

---

## 5. Selected Baseline

| Field | Value |
|---|---|
| **Task** | Binary wound segmentation |
| **Dataset** | DFUC2022 (demo split, 20 samples) |
| **Annotation type** | Binary segmentation masks (PNG, {0, 255}) |
| **Input** | RGB image, 256 × 256 (resized from 512 × 512 for CPU feasibility) |
| **Output** | Binary probability map: shape (1, 256, 256), sigmoid-activated |
| **Model** | Lightweight UNet — 4 encoder levels, 4 decoder levels, skip connections |
| **Loss** | Binary Cross-Entropy + Dice Loss (combined) |
| **Pretrained weights** | None (randomly initialized) — see rationale below |
| **Checkpoint selection** | Best validation Dice score |
| **Primary metric** | Dice coefficient on test split |

---

## 6. Pretrained Weights Decision (REQ-P02-S01-005)

**Decision: No pretrained weights for this baseline.**

**Rationale:**
- The baseline must be "materially simpler" than later advanced models (REQ-P02-S01-004).
- Using pretrained ImageNet weights from a large backbone would make the baseline less interpretable and closer to an advanced model.
- Random initialization on 20 samples will overfit, which is expected and documentable behavior for a baseline.
- Phase 03+ will introduce pretrained encoders (e.g., ResNet-34 ImageNet backbone) as an explicit improvement.
- This allows clean attribution of improvement: random init → pretrained weights.

**If pretrained weights were to be used:** Source would be `torchvision.models.resnet34(pretrained=True)` (ImageNet weights, MIT-compatible), frozen encoder, fine-tuned decoder.

---

## 7. Baseline Limitations

1. **Very small dataset (20 samples):** Meaningful generalization is impossible. Results are for system validation only.
2. **Image-level split (not patient-level):** Some data leakage risk exists. Documented in Phase 01 manifest.
3. **Demo images are synthetic/uniform:** DFUC22_0001–DFUC22_0020 all have the same checksum for images, meaning they are likely template/demo files. Metric numbers reflect model behavior on this toy data, NOT real DFUC2022.
4. **CPU-only training:** Small batch size and fewer epochs; may not converge fully.
5. **No augmentation complexity:** Minimal augmentation to keep baseline simple.
6. **Wound area imbalance:** ~15% foreground. Standard BCE will tend toward predicting background. Dice loss component mitigates this.

---

## 8. Later Improvement Path

1. **More data:** Use full DFUC2022 dataset (real images, ~4,000 samples) when available.
2. **Pretrained encoder:** Replace random init with ImageNet-pretrained ResNet-34 encoder.
3. **Advanced loss:** Focal loss or combined Dice+Focal for stronger imbalance handling.
4. **Augmentation:** Add elastic deformation, color jitter, rotation for medical image augmentation.
5. **Post-processing:** Connected components filtering to remove small spurious predictions.
6. **Patient-level split:** When patient metadata is available, enforce patient-level isolation.

---

## 9. Open Questions Resolution

| OQ ID | Question | Resolution |
|---|---|---|
| OQ-P02-001 | Best baseline task? | RESOLVED: Wound segmentation — all Phase 01 annotations are binary masks |
| OQ-P02-002 | Best baseline architecture? | RESOLVED: Lightweight UNet — standard medical segmentation baseline |
| OQ-P02-003 | Pretrained weights? | RESOLVED: None for baseline — allows clean Phase 03 improvement attribution |
| OQ-P02-004 | Input resolution? | RESOLVED: 256×256 — reasonable for CPU training; downsampled from 512×512 |
| OQ-P02-005 | Augmentation? | RESOLVED: Horizontal flip + random crop (train only); none for val/test |
| OQ-P02-006 | Class imbalance strategy? | RESOLVED: Dice loss component in combined BCE+Dice loss handles imbalance |
| OQ-P02-007 | Metric aggregation? | RESOLVED: Macro-average per-sample Dice/IoU across test set |
| OQ-P02-008 | Failure modes? | OPEN — to be filled after baseline training run |

---

## 10. REQ-P02-S01-007 Compliance

No test-set performance was inspected to make this decision.  
The architecture, preprocessing, and hyperparameter choices are based solely on:
- Phase 01 annotation evidence (manifest, quality report, EDA summary)
- Engineering rationale (compute budget, simplicity requirement, literature consensus)
- The spec requirement that the baseline be materially simpler than later models

**No test split was examined.**
