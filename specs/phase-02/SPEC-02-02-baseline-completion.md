# SPEC-02-02 — Baseline Run, Evaluation, and Error Review

## Status

`COMPLETED` (2026-10-22), executed by SPEC-02-03 on the authorized held-out
split `fuseg2021-heldout-v1`. Evidence: `reports/experiments/spec_02_03_report.md`.

Requirements coverage:

| Requirement | How it was met |
|---|---|
| 001 | Approved manifest and config only |
| 002 | Checkpoint selected on internal-val Dice |
| 003 | Resume verified by the CPU train-and-resume unit test. The Kaggle run was not interrupted, so resume was not exercised there. |
| 004 | Held-out test provenance recorded |
| 005 | Per-sample and aggregate metrics with counts |
| 006 | Error review separates observed errors from hypotheses |
| 007 | Every metric was recomputed independently on CPU |

The optional from-scratch SPEC-02-01 re-run on the held-out manifest was not
performed.

## Objective

Complete the real FUSeg2021 baseline after the SPEC-02-01 engineering gate.

## Scope

- Kaggle GPU train/validation run using the approved configuration.
- Validation-Dice checkpoint selection and interruption/resume verification.
- Evaluation on an authorized labeled evaluation set only.
- Per-sample metrics, aggregate metrics, qualitative review, error categories,
  and reproducibility record.

## Non-Goals

- Training on CPU.
- Treating public unlabeled FUSeg2021 test images as ground truth.
- Advanced architectures, tissue analysis, or Phase 03 implementation.

## Requirements

- **REQ-SPEC-02-02-001:** The run SHALL use only the approved FUSeg2021
  manifest and configuration.
- **REQ-SPEC-02-02-002:** The best checkpoint SHALL be selected using validation
  Dice only.
- **REQ-SPEC-02-02-003:** A latest checkpoint SHALL permit interruption-safe
  resume with model, optimizer, scheduler, RNG, and DataLoader state.
- **REQ-SPEC-02-02-004:** Evaluation SHALL use only an authorized labeled split
  and SHALL record its provenance.
- **REQ-SPEC-02-02-005:** Metrics SHALL include per-sample Dice, IoU, precision,
  recall, aggregate values, and sample counts.
- **REQ-SPEC-02-02-006:** Qualitative findings SHALL be based on saved
  predictions and SHALL distinguish observed errors from hypotheses.
- **REQ-SPEC-02-02-007:** No unsupported or fabricated metric SHALL appear in
  the final record.

## Evaluation split (decision required — added 2026-10-21)

**Problem.** REQ-SPEC-02-02-004 requires an "authorized labeled split", but no
such split currently exists:

- The FUSeg2021 public test masks are not released.
- The official validation split is used for checkpoint selection and
  ReduceLROnPlateau. Any metric reported on it is optimistically biased.

Without a decision this spec cannot reach `COMPLETED`.

**Resolution (IMPLEMENTED in SPEC-02-03, 2026-10-21):** the split below is
implemented as `data/manifests/fuseg2021_heldout_manifest.json`
(`fuseg2021-heldout-v1`). It adds near-duplicate grouping and test-neighbour
quarantine; see `specs/phase-02/SPEC-02-03-strong-segmentation.md`. The
pretrained SPEC-02-03 model is the primary result. The SPEC-02-01 baseline may
be re-run on the same held-out manifest as a from-scratch reference.

Original proposal, now adopted:

1. Carve a deterministic internal validation subset (about 15%, seeded and
   recorded in the manifest) out of the official FUSeg2021 **train** split. Use
   it for checkpoint selection and the LR schedule.
2. Treat the official FUSeg2021 **validation** split (191 usable pairs) as the
   held-out **test** set. Evaluate it once, after training is frozen.
3. Report two numbers:
   - the macro per-image Dice (current definition);
   - the dataset-level (pooled) Dice, which is the convention most published
     FUSeg results use.

   Also report the non-empty subset separately.
4. Optionally, run 5-fold cross-validation on train to get a variance estimate.

Until this is approved, any validation-split number must be labelled
"validation (used for model selection)", never "test".

## Dependencies

SPEC-02-01, verified FUSeg2021 manifest, Kaggle CUDA runtime, and authorized
labeled evaluation data.

## Outputs and Evidence

Best/latest checkpoints, training log, evaluation JSON, qualitative panels,
error-review report, reproducibility record, and updated traceability.

## Tests and Acceptance

The specification is complete only when the Kaggle command succeeds, resume is
verified, all required artifacts exist, metrics are independently checked, and
the report explicitly records the public-test label limitation.

## Reproducibility and Limitations

Record the exact config, manifest digest, code revision, environment, seed,
commands, checkpoint paths, and evaluation data provenance. Technical results
do not establish clinical efficacy.
