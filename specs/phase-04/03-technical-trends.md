# P04-S03 — Technical Trend Outputs

## Status

`COMPLETED` — `src/longitudinal/trends.py` builds ordered per-examination series, changes from baseline and from the previous point, explicit exclusions, and an optional plot labelled as a technical trend. Tests: `tests/longitudinal/test_p04_longitudinal.py`, API end to end in `tests/api/test_p05_api.py`.

## Objective

Represent image-derived measurement changes over available examinations as
technical trends.

## Scope

Area change, percentage change, perimeter/boundary change, trend tables, plots,
warnings, and non-clinical presentation language.

## Non-Goals

Healing diagnosis, prognosis, treatment recommendation, or clinical outcome
claims.

## Requirements

- **REQ-P04-S03-001:** Trend values SHALL be calculated from stored compatible
  measurements only.
- **REQ-P04-S03-002:** Denominator-zero and missing-data cases SHALL be
  explicitly represented.
- **REQ-P04-S03-003:** Output text SHALL identify results as image-derived
  technical trends.
- **REQ-P04-S03-004:** Trend artifacts SHALL be reproducible from the source
  examination records.

## Tests and Acceptance

Known time-series fixtures, no-baseline cases, missing-data cases, and output
reproducibility tests SHALL pass.
