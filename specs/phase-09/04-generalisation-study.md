# P09-S04 — External Generalisation Study

**Status:** `NOT_STARTED`. Nothing in this specification is implemented. It needs approval before work begins.

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

## 17. Reproducibility

Planned commands. These do not work until the specification is implemented.

```bash
python scripts/data/check_near_duplicates.py
python scripts/training/run_spec_02_03.py --train --evaluate --external
```

## 18. Risks / Limitations

- Sources share images, so leakage is a real risk.
- GPU limits bound the search.
- Improvement is not guaranteed.

## 19. Traceability

| Requirement | Planned implementation | Planned test | Planned evidence | Status |
|---|---|---|---|---|
| `REQ-P09-S04-001` | `reports/experiments/p09_s04_protocol.md` | Review of the protocol | Study report | NOT_STARTED |
| `REQ-P09-S04-002` | `data/manifests/` | Split leakage test | Manifest | NOT_STARTED |
| `REQ-P09-S04-003` | `scripts/evaluation/` | Evaluation run | Comparison report | NOT_STARTED |
| `REQ-P09-S04-004` | `docs/deployment/MODEL_CARD.md` | Claim-check test | Model card | NOT_STARTED |
| `REQ-P09-S04-005` | `configs/inference/` | Hash test | Release record | NOT_STARTED |
