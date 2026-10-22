# Phase 00 — Open Questions

This document tracks unresolved decisions instead of hiding uncertainty inside implementation.

Status reconciled on 2026-10-21 against the Phase 01 and Phase 02 outcomes.

| ID | Question | Why It Matters | Status | Decision |
|---|---|---|---|---|
| OQ-001 | Which exact official dataset versions/access routes will be used? | Determines reproducibility and acquisition pipeline. | RESOLVED | Pinned commits, DOI and snapshot are in `data/external/dataset_registry.json` v2.0.0. DFUC is blocked by license. See OQ-P01-001. |
| OQ-002 | Which datasets expose reliable patient/examination identifiers? | Determines patient-level split and leakage strategy. | RESOLVED (limitation) | None of the acquired datasets do. Splits are image-level. See OQ-P01-003 and OQ-P01-006. |
| OQ-003 | What exact target classes/label semantics will be used for each task? | Prevents incompatible labels across datasets. | RESOLVED for MVP | MVP uses binary wound vs background (FUSeg2021). Tissue classes are deferred. See OQ-P01-004. |
| OQ-004 | Is physical wound scale available or will MVP remain pixel-based? | Determines whether physical dimensions can be reported. | RESOLVED (pixel-based) | MVP is pixel-based. Physical units require a separate calibration spec. See OQ-P01-007. |
| OQ-005 | Which components are mandatory MVP versus advanced experiments after dataset verification? | Controls project scope. | RESOLVED | See `specs/REVISED_ROADMAP.md`: segmentation, quality gate, measurement, longitudinal comparison, API and dashboard are mandatory. Detection and tissue analysis are optional. |
| OQ-006 | What deployment target is justified by measured inference requirements? | Prevents premature optimization. | OPEN | To be decided in P06-S02 from measured latency and memory. |
| OQ-007 | What image-quality thresholds should be used? | Requires data-driven calibration. | OPEN | To be calibrated in P03-S02. Candidate fixture sources are Medetec and LowerLimb. |

## Rule

An open question may remain unresolved when it genuinely requires information from later experiments. It must not be silently converted into an assumption.
