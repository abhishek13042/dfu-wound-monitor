# Phase 02 — Open Questions

Do not invent answers. Resolve only with Phase 01 evidence or an explicit
engineering decision.

## OQ-P02-001 — Baseline task

**Status: RESOLVED** — FUSeg2021 provides pixel masks, so binary wound
segmentation is selected for SPEC-02-01.

## OQ-P02-002 — Baseline architecture

**Status: RESOLVED** — An explicit four-level lightweight U-Net is selected and
implemented with configurable channel widths.

## OQ-P02-003 — Pretrained weights

**Status: RESOLVED** — No pretrained weights are used in the baseline.

## OQ-P02-004 — Input resolution

**Status: RESOLVED** — The real run uses configurable 256 × 256 preprocessing,
with source images verified at 512 × 512.

## OQ-P02-005 — Augmentation

**Status: RESOLVED** — Training uses seeded synchronized horizontal flipping at
the configured probability; validation has no random augmentation.

## OQ-P02-006 — Class imbalance and empty masks

**Status: RESOLVED** — The loss is equal-weight BCEWithLogits plus soft Dice.
Empty masks are valid source annotations and are retained; the loss and metrics
have explicit finite empty-mask behavior.

## OQ-P02-007 — Metric aggregation

**Status: RESOLVED** — Validation metrics use macro-averages of per-sample Dice,
IoU, precision, and recall at a preconfigured threshold of 0.5.

## OQ-P02-008 — Observed failure modes

**Status: OPEN** — Qualitative validation predictions are produced by the real
run. A full error review remains outside this implementation report until the
prediction artifacts are inspected as part of the later evaluation scope.

## OQ-P02-009 — FUSeg2021 public test labels

**Status: RESOLVED** — The public test directory contains 200 images and no
usable ground-truth masks. SPEC-02-01 does not evaluate them as labeled data.

## OQ-P02-010 — Patient-level grouping

**Status: RESOLVED WITH LIMITATION** — The public release provides no usable
patient or examination identifiers. Official split assignments are preserved,
but patient-level isolation is not claimed.

## OQ-P02-011 — Exact duplicate images

**Status: RESOLVED** — Exact duplicate image groups are reported and later
occurrences are quarantined without modifying raw files. The final manifest
passes cross-split image/path/checksum leakage checks.
