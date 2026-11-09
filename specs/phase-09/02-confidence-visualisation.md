# P09-S02 — Model Confidence Visualisation

**Status:** `COMPLETED`. All four requirements are built and tested, and the study on internal validation decided that the summary value is shown. See §16 for what was and was not run.

## 1. Objective

Show users where the model is less certain, without presenting that as clinical confidence.

## 2. Scope

- Heatmap from the stored probability map
- Summary signal from TTA disagreement
- Calibration check of the signal on internal validation

## 3. Non-Goals

- Bayesian models or ensembles
- Using uncertainty to reject images before a study supports it
- Any clinical confidence statement

## 4. Requirements

- `REQ-P09-S02-001`: The result page SHALL offer a heatmap overlay of the stored probability map.
- `REQ-P09-S02-002`: The service SHALL compute a TTA disagreement summary and store it with the analysis.
- `REQ-P09-S02-003`: The relation between the signal and Dice SHALL be measured on internal validation and reported before the signal is shown as meaningful.
- `REQ-P09-S02-004`: The UI SHALL describe the signal as model uncertainty and SHALL NOT state a probability that the result is correct.

## 5. Assumptions

- Flip TTA gives four views (identity, horizontal, vertical, both) to compare. This is weak evidence of uncertainty, and the study decides its value.

## 6. Dependencies

- `P03-S01`
- `P08-S02`

## 7. Inputs

- Probability maps
- Internal validation set of 118 images

## 8. Outputs

- Heatmap
- `uncertainty` field
- Study report

## 9. Data / Interface Contract

`inference.uncertainty` is added to the analysis response, inside the stored inference summary, so no migration is needed. The field is additive, so existing clients keep working. It is `null` when TTA is off.

```json
{"tta_disagreement": 0.0184, "method": "flip_tta_v1", "views": 4, "region": "MASK_AND_BAND", "band_px": 8,
 "region_pixels": 51234, "empty_mask": false, "config_version": "p09-s02-v1", "summary_shown": true}
```

`region` is `MASK_AND_BAND`, or `WHOLE_IMAGE` with `empty_mask: true` when the prediction is empty. `summary_shown` comes from `configs/inference/uncertainty_v1.json`, which must match the study's decision.

## 10. Invariants

- The field never changes the mask or measurements.
- The held-out test set is not used for selecting a signal.

## 11. Technical Design

Disagreement is the mean absolute difference between every pair of the four flip-TTA probability maps (each flipped back), at model resolution, inside the predicted region dilated by an 8-pixel elliptical band. The views are the ones the engine already computes for TTA, so it adds no inference; their mean is still the probability map the mask is cut from, bit for bit (`src/segmentation/inference.py` `mean_of_views`). The ONNX engine returns the same views.

The heatmap draws the existing probability PNG on a canvas in the single `--series` hue, with each pixel's alpha set to its score, and a 0 to 1 legend. An Outline / Heatmap toggle on the result page switches between it and the mask; the opacity slider applies to both. Without a signed URL (mock mode) a soft constructed shape stands in. The summary is shown in a "Model uncertainty" panel only when `summary_shown` is true.

## 12. Implementation Tasks

1. Add the disagreement summary.
2. Run the study on internal validation.
3. Build the heatmap.
4. Write the UI text.

## 13. Failure Modes / Edge Cases

| Case | Required behaviour |
|---|---|
| Empty mask | Report over the whole image and flag the case |
| Weak study result | Keep the heatmap and do not display the summary value |

## 14. Tests

- Known-input maths
- Additive-field contract
- Language test

## 15. Acceptance Criteria

- The study report exists and decides whether the summary is shown.

## 16. Evidence

Recorded on 2026-11-05.

- **Study (REQ-003):** `reports/final/p09_s02_uncertainty.json`, FUSeg2021 `internal_val`, 118 images, CPU, 330 s. The held-out test split was not loaded.
  - Spearman rho between disagreement and Dice: **−0.659**, bootstrap 95% CI −0.771 to −0.517 (2000 resamples, seed 20261105).
  - The rule fixed before the run (rho ≤ −0.3 and CI upper bound < 0) passed, so `summary_shown` is `true`.
  - AUROC for flagging the 3 images with Dice < 0.5: 0.675. One image had an empty prediction.

  | Disagreement quartile | Range | Mean Dice | Median Dice |
  |---|---|---|---|
  | 1 (lowest) | 0.000 to 0.017 | 0.931 | 0.964 |
  | 2 | 0.017 to 0.026 | 0.934 | 0.948 |
  | 3 | 0.027 to 0.043 | 0.905 | 0.934 |
  | 4 (highest) | 0.044 to 0.224 | 0.782 | 0.843 |

  The signal mostly separates the worst quarter; it does not rank the better three quarters.
- **Tests (REQ-002):** `tests/inference/test_uncertainty.py`, 10 passed: known maths, the pairwise average, identical views, the empty mask, one view, shape mismatch, bad config, the engine summary with the mask unchanged bit for bit, no summary without TTA, and the shown flag matching the report. Regression across `tests/inference`, `tests/api` and `tests/worker`: 157 passed.
- **Web (REQ-001, REQ-004):** `npx tsc --noEmit` clean, `npm run test:wording` passed (it now also rejects confidence or chance-of-being-correct wording), vitest 25 passed, Playwright pages 46 passed including the new heatmap test with axe. In the browser at 1280 px and 375 px the toggle drew the heatmap, the panel showed the value with its wording, and nothing scrolled sideways. `impeccable detect` exited 0.
- **Not run:** the live path, where the canvas decodes a stored probability PNG from the service, was checked only by reading the code; the browser checks used mock mode.

## 17. Reproducibility

```bash
python scripts/evaluation/run_uncertainty_study.py            # about 2.8 s per image on CPU
python -m pytest tests/inference/test_uncertainty.py -q
cd web && npm run -s test:wording && npx playwright test --project=pages
```

After a new study run, set `summary_shown` in `configs/inference/uncertainty_v1.json` to the report's `decision.show_summary`; `test_the_shown_flag_follows_the_study_decision` fails until they agree.

## 18. Risks / Limitations

- Users may read a heatmap as clinical certainty. On external data, the signal may not track error. The study used internal validation from the same source as training.
- The browser decodes the 16-bit PNG to 8 bits, so the heatmap shows 256 levels. That is enough to see, not to measure.
- The value is shown without a reference band. Users get a sentence that higher values went with less accurate outlines, not a cut-off.

## 19. Traceability

| Requirement | Implementation | Test | Evidence | Status |
|---|---|---|---|---|
| `REQ-P09-S02-001` | `web/components/Heatmap.tsx`, `web/components/MaskOverlay.tsx` | `e2e/pages.spec.ts` heatmap test | Playwright run, §16 | COMPLETED |
| `REQ-P09-S02-002` | `src/inference/uncertainty.py`, `src/inference/engine.py` | `tests/inference/test_uncertainty.py` | Test run, §16 | COMPLETED |
| `REQ-P09-S02-003` | `scripts/evaluation/run_uncertainty_study.py` | Study run, `test_the_shown_flag_follows_the_study_decision` | `reports/final/p09_s02_uncertainty.json` | COMPLETED |
| `REQ-P09-S02-004` | `web/components/Heatmap.tsx` | `web/scripts/check-wording.mjs`, `e2e/pages.spec.ts` | Wording check and Playwright run, §16 | COMPLETED |
