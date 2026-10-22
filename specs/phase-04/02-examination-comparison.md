# P04-S02 — Multi-Examination Alignment and Comparison

## Status

`COMPLETED` — `src/longitudinal/comparison.py`. Its explicit `CompatibilityPolicy` makes a comparison UNAVAILABLE, with a reason code, when the model version, calibration, case or status make the values non-comparable. Every output carries a technical-only label. Tests: `tests/longitudinal/test_p04_longitudinal.py`.

## Objective

Compare compatible examinations without pretending that unrelated images form a
clinical longitudinal cohort.

## Scope

Identity and time compatibility, pairwise comparison, missing visits,
calibration changes, model-version incompatibility, and comparison warnings.

## Non-Goals

Clinical healing classification or automatic treatment recommendations.

## Requirements

- **REQ-P04-S02-001:** Comparisons SHALL require a valid compatibility policy.
- **REQ-P04-S02-002:** Missing identity, timestamps, calibration, or compatible
  measurements SHALL produce an explicit unavailable/warning state.
- **REQ-P04-S02-003:** The comparison SHALL preserve both source examination
  references and model versions.
- **REQ-P04-S02-004:** No cross-dataset sample SHALL be presented as a patient
  trajectory without verified linkage.

## Tests and Acceptance

Fixtures SHALL cover valid pairs, missing visits, changed calibration,
incompatible models, unknown identity, and deterministic comparison values.
