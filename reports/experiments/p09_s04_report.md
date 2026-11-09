# P09-S04 — Annotation-protocol hypothesis: result

Recorded on 2026-11-05. Protocol: `reports/experiments/p09_s04_protocol.md`, frozen before the run, with no changes after freezing.
Data: `reports/final/p09_s04_annotation_hypothesis.json` (numbers only). Log: `reports/final/p09_s04_run.log`.

## Question

The v1.0.0 model scores pooled Dice 0.922 on the FUSeg2021 held-out test, but **0.26** on 148 external LowerLimb V3 images.
Precision is 0.90 and recall 0.15, so the model misses most of the labelled area.

- **H1:** the native-331 LowerLimb masks label a wider region than FUSeg does, including the skin around the wound. The model is then "missing" area it was never trained to mark.
- **H0:** the model fails to find wound tissue in images from a new source, which is a real generalisation gap.

No model was trained or tuned. The frozen v1.0.0 model and threshold predicted each accepted P06 external image again.

## Results

| Measure | native_331 (n = 132) | resized_224 (n = 16) | FUSeg2021 test (n = 186 non-empty) |
|---|---|---|---|
| Label area share, median | 0.077 | 0.030 | 0.007 |
| Label solidity, median | 0.815 | 0.889 | 0.912 |
| Mean probability in the missed region, median | 0.007 | 0.084 | — |
| T1 eligible images | 78 | 11 | — |
| T1 share of missed regions that look like skin | **0.718** | 0.636 | — |

**T1, colour (supports H1).** In 72 % of the 78 eligible native-331 images, the missed part of the label is closer in colour (CIELAB ΔE) to the skin ring just outside the label than to the part the model did find. The fixed bar was 60 %.

**T2, shape (does not support H1).** Native-331 labels were predicted to be more convex (rounder outlines drawn around the wound). They are less convex: median solidity 0.815 against FUSeg's 0.912, a difference of −0.097. The bar was +0.05.

**Outcome, by the frozen decision table: H1 partly supported.**

## What it means

- The native labels are about **ten times larger**, as a share of the image, than FUSeg labels, and most of the missed area looks like skin. The model is confident it is not wound there: median probability 0.007.
- So a large part of the 0.26 is a difference in what is labelled, not tissue the model fails to see. This agrees with P06, where the 16 FUSeg-style LowerLimb masks scored 0.82.
- The shape prediction was wrong. The native labels are wider but irregular, not neat outlines around the wound. H1 as written, a "rounded margin drawn around the wound", is not what the data show.
- This is still not proof that the model generalises. The colour test says the missed region resembles skin; it does not say no wound tissue is in it. Only a relabelling or a new external set can show that.

## What does not change

- The v1.0.0 external result of **0.26** stays published, beside this study, in `docs/deployment/MODEL_CARD.md`.
- No new model was trained. v1.0.0 stays in production.

## Next steps, and what blocks them

| Step | Status | Needs |
|---|---|---|
| Relabel a sample of LowerLimb images in the FUSeg style, then score | `BLOCKED` | A clinician or trained annotator |
| A new external set, or a new patient-grouped split fixed before training (REQ-002) | `BLOCKED` | A new licensed source; LowerLimb V3 has been seen and cannot serve again |
| Combined-source training and appearance augmentation (REQ-003) | `BLOCKED` | Kaggle GPU time and the new external set |
| A new model version and card entry (REQ-005) | Not applicable until a candidate exists | — |

## Limits

- One source (LowerLimb V3), with 148 accepted images. Only 78 native-331 images had large enough hit, missed and ring regions for T1.
- Mean colour per region is coarse. Lighting and skin tone differ between images.
- Solidity uses only the largest part of each label.
