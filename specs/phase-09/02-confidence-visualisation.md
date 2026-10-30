# P09-S02 — Model Confidence Visualisation

**Status:** `NOT_STARTED`. Nothing in this specification is implemented. It needs approval before work begins.

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

- Flip TTA gives two predictions to compare. This is weak evidence of uncertainty, and the study decides its value.

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

`uncertainty: {tta_disagreement: float, method: "flip_tta_v1"}` is added to the analysis response. The field is additive, so existing clients keep working.

## 10. Invariants

- The field never changes the mask or measurements.
- The held-out test set is not used for selecting a signal.

## 11. Technical Design

Disagreement is the mean absolute difference between the two TTA probability maps, inside the predicted region and a narrow band around it. The heatmap uses the existing probability PNG, so it needs no new inference.

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

- `reports/final/p09_s02_uncertainty.json`

## 17. Reproducibility

Planned commands. These do not work until the specification is implemented.

```bash
python scripts/evaluation/run_uncertainty_study.py
```

## 18. Risks / Limitations

- Users may read a heatmap as clinical certainty. On external data, the signal may not track error.

## 19. Traceability

| Requirement | Planned implementation | Planned test | Planned evidence | Status |
|---|---|---|---|---|
| `REQ-P09-S02-001` | `web/components/Heatmap.tsx` | Component test | Test report | NOT_STARTED |
| `REQ-P09-S02-002` | `src/inference/uncertainty.py` | `test_disagreement_known_inputs` | Test run | NOT_STARTED |
| `REQ-P09-S02-003` | `scripts/evaluation/run_uncertainty_study.py` | Study run | `reports/final/p09_s02_uncertainty.json` | NOT_STARTED |
| `REQ-P09-S02-004` | `web/components/Heatmap.tsx` | Language test | Test report | NOT_STARTED |
