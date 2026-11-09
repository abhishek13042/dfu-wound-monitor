# P09-S04 — External Generalisation Study

**Status:** `IN_PROGRESS`. The annotation hypothesis was tested under a frozen protocol, and the outcome is reported: **H1 partly supported** (REQ-001 and REQ-004 `COMPLETED`). Training work is `BLOCKED` (REQ-002, REQ-003, REQ-005). It needs a new external set or relabelled masks, and Kaggle GPU time.

## 1. Objective

Find out why external Dice falls to 0.26, then try to improve it under a protocol that cannot leak.

## 2. Scope

- Test of the annotation-protocol hypothesis
- Training with extra sources
- Stronger domain augmentation
- A new held-out external design
- DFUC data if the licence is granted

## 3. Non-Goals

- Rewriting or hiding the v1.0.0 result
- Tuning on any final test set
- Replacing the production model without P10-S04 promotion

## 4. Requirements

- `REQ-P09-S04-001`: The hypothesis SHALL be tested with a written protocol, and the outcome SHALL be reported whether or not it holds.
- `REQ-P09-S04-002`: LowerLimb V3 has been seen and SHALL NOT be used again as an untouched external test. A new external set, or a new patient-grouped split fixed before training, SHALL serve instead.
- `REQ-P09-S04-003`: Each candidate SHALL be compared with v1.0.0 on the same held-out data and the same metrics.
- `REQ-P09-S04-004`: The v1.0.0 external result SHALL stay published beside any new result.
- `REQ-P09-S04-005`: A new model SHALL have its own version, checkpoint hash and model card entry.

## 5. Assumptions

- Kaggle GPU time is available.
- DFUC2020, DFUC2021 and DFUC2022 remain BLOCKED until the licence is granted, and the study must work without them.
- Medetec and DFUTissueSegNet can be used if their terms allow it.

## 6. Dependencies

- `SPEC-02-03`
- `P06-S01`

## 7. Inputs

- FUSeg2021
- LowerLimb V3
- Medetec
- DFUTissueSegNet
- DFUC data if licensed

## 8. Outputs

- Protocol
- Comparison report
- A new checkpoint, only if justified

## 9. Data / Interface Contract

Every experiment records dataset versions, split hashes, config and seed, as SPEC-02-03 does.

## 10. Invariants

- Hypotheses stay separate from measured results.
- The test set is scored once per final candidate.
- No result is removed because it is unfavourable.

## 11. Technical Design

Start with analysis that needs no training: compare mask styles, then retrain only if that shows a real shift. Then try combined-source training and appearance augmentation. Use the resized-224 and native-331 mask groups from Phase 06 as separate strata, not as one mixed score.

As built:

- **`reports/experiments/p09_s04_protocol.md`:** frozen before the run. It states H1 and H0, two tests with fixed bars, and a decision table.
  - **T1, colour:** in each native-331 image, is the labelled-but-missed region closer in CIELAB colour to the skin ring 5–15 px outside the label than to the region the model found? H1 is supported if at least 60 % of eligible images say yes.
  - **T2, shape:** H1 is supported if the median native-331 label solidity is at least 0.05 above FUSeg2021's.
- **`scripts/evaluation/run_annotation_hypothesis.py`:** reruns the frozen v1.0.0 model and threshold on the 148 accepted P06 external images, in both strata. No training or tuning. It writes numbers only.

## 12. Implementation Tasks

1. Write and freeze the protocol.
2. Test the annotation hypothesis.
3. Fix the new external split.
4. Train candidates.
5. Score once and report.

## 13. Failure Modes / Edge Cases

| Case | Required behaviour |
|---|---|
| Hypothesis rejected | Report it and update the known gaps |
| No improvement | Keep the v1.0.0 model and report the null result |
| Licence refused | Continue without DFUC |

## 14. Tests

- Leakage tests across all sources
- Near-duplicate checks
- Independent metric recomputation

## 15. Acceptance Criteria

- The report answers the hypothesis question with evidence.
- Any improvement claim survives independent recomputation.

## 16. Evidence

- `reports/experiments/p09_s04_report.md`

Recorded on 2026-11-05.

- **Run:** complete, 148 images (`reports/final/p09_s04_annotation_hypothesis.json`, log `reports/final/p09_s04_run.log`).
- **T1, colour:** 71.8 % of 78 eligible native-331 images have a skin-like missed region. That passes the 60 % bar and supports H1. Resized-224: 63.6 % of 11.
- **T2, shape:** native-331 median solidity 0.815 against FUSeg2021's 0.912, a difference of −0.097. That fails the +0.05 bar: native labels are less convex, the opposite of the prediction.
- **Outcome:** H1 partly supported.
  - Native-331 labels cover a median 7.7 % of the image against 0.7 % for FUSeg2021.
  - In the missed region the model's median probability is 0.007, so it is confident there is no wound there.
- **Model card:** the 0.26 stays, with the study beside it.
- **Tests:** `tests/unit/test_annotation_hypothesis.py`, 3 passed.
- **Not done:** the new external split, candidate training and a new model. See §18.

## 17. Reproducibility

```bash
python -m pytest tests/unit/test_annotation_hypothesis.py -q
python scripts/evaluation/run_annotation_hypothesis.py
# once a new external set and GPU time exist (BLOCKED):
python scripts/data/check_near_duplicates.py
python scripts/training/run_spec_02_03.py --train --evaluate --external
```

## 18. Risks / Limitations

- Sources share images, so leakage is a real risk.
- GPU limits bound the search.
- Improvement is not guaranteed.
- The colour test shows that the missed region looks like skin. It does not show that no wound tissue is in it. A FUSeg-style relabelling by a clinician would settle that, and it is `BLOCKED`.
- Only 78 of 132 native-331 images had large enough regions for T1.
- REQ-002 is `BLOCKED`: LowerLimb V3 cannot serve as an untouched test again, and no new licensed source is available. REQ-003 and REQ-005 are `BLOCKED` because there is no GPU time and no candidate.

## 19. Traceability

| Requirement | Implementation | Test | Evidence | Status |
|---|---|---|---|---|
| `REQ-P09-S04-001` | `reports/experiments/p09_s04_protocol.md`, `scripts/evaluation/run_annotation_hypothesis.py` | `tests/unit/test_annotation_hypothesis.py`; study run 2026-11-05 | `reports/experiments/p09_s04_report.md` | COMPLETED |
| `REQ-P09-S04-002` | `data/manifests/` | Split leakage test | Manifest | BLOCKED |
| `REQ-P09-S04-003` | `scripts/evaluation/` | Evaluation run | Comparison report | BLOCKED |
| `REQ-P09-S04-004` | `docs/deployment/MODEL_CARD.md` | Model card keeps 0.26 beside the study | Model card | COMPLETED |
| `REQ-P09-S04-005` | `configs/inference/` | Hash test | Release record | BLOCKED |
