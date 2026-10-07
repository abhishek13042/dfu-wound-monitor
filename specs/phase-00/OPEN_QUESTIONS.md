# Phase 00 — Open Questions

This document tracks unresolved decisions instead of hiding uncertainty inside implementation.

| ID | Question | Why It Matters | Status | Decision |
|---|---|---|---|---|
| OQ-001 | Which exact official dataset versions/access routes will be used? | Determines reproducibility and acquisition pipeline. | OPEN | |
| OQ-002 | Which datasets expose reliable patient/examination identifiers? | Determines patient-level split and leakage strategy. | OPEN | |
| OQ-003 | What exact target classes/label semantics will be used for each task? | Prevents incompatible labels across datasets. | OPEN | |
| OQ-004 | Is physical wound scale available or will MVP remain pixel-based? | Determines whether physical dimensions can be reported. | OPEN | |
| OQ-005 | Which components are mandatory MVP versus advanced experiments after dataset verification? | Controls project scope. | OPEN | |
| OQ-006 | What deployment target is justified by measured inference requirements? | Prevents premature optimization. | OPEN | |
| OQ-007 | What image-quality thresholds should be used? | Requires data-driven calibration. | OPEN | |

## Rule

An open question may remain unresolved when it genuinely requires information from later experiments. It must not be silently converted into an assumption.
