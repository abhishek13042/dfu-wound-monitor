# P05-S03 — Minimal Monitoring Dashboard

## Status

`COMPLETED` — `src/dashboard/index.html`, served at `/dashboard`. It covers cases, examinations, upload with optional calibration, overlay, measurements, warnings and limitations, provenance, trend, and deletion. It uses only the public API, which `tests/api/test_p05_api.py` checks. Exercised in a browser against the real model.

## Objective

Demonstrate the end-to-end technical workflow through a minimal user-facing
dashboard.

## Scope

Select/upload examination, display quality status, segmentation overlay,
measurements, provenance, and available longitudinal comparisons.

## Non-Goals

Clinical decision support, treatment advice, direct model invocation, or a
feature-rich production frontend.

## Requirements

- **REQ-P05-S03-001:** The dashboard SHALL communicate through the API only.
- **REQ-P05-S03-002:** Quality rejection and model/infrastructure failures SHALL
  be displayed distinctly.
- **REQ-P05-S03-003:** Measurements SHALL show units/calibration status and
  limitations.
- **REQ-P05-S03-004:** Missing longitudinal data SHALL be represented honestly.

## Tests and Acceptance

Component, API integration, error-state, provenance-display, and one complete
demo workflow tests SHALL pass.
