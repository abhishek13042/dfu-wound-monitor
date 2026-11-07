# P09-S01 — Reference-Marker Calibration

**Status:** `IN_PROGRESS`. Marker detection, the fallbacks with reason codes, the conflict warning, the printable sheet, the validation script and the web display are built, with 18 tests. REQ-P09-S01-003 is `BLOCKED`: it needs real photos of the printed marker beside objects of known size. A synthetic run of the same script exists and is labelled as such.

## 1. Objective

Produce physical measurements from a printed reference marker in the photo, with a measured error.

## 2. Scope

- ArUco marker detection with OpenCV
- Printable marker sheet
- `pixels_per_mm` from marker corners
- Quality checks for tilt and marker size
- Measured-error test set

## 3. Non-Goals

- 3D reconstruction or foot-curvature correction
- Any claim of clinical measurement accuracy
- Ruler detection

## 4. Requirements

- `REQ-P09-S01-001`: A detected marker SHALL produce `pixels_per_mm` with `calibration_method` set to `ARUCO_MARKER` and the marker ID as its source.
- `REQ-P09-S01-002`: A missing, partial, or too-small marker, or excess tilt, SHALL fall back to pixels with a reason code. The system SHALL NOT guess a scale.
- `REQ-P09-S01-003`: Calibration error SHALL be measured on photos of objects of known size, across distances and angles, and reported with its range.
- `REQ-P09-S01-004`: A user-entered scale SHALL NOT silently override a detected marker. Disagreement SHALL produce a warning.
- `REQ-P09-S01-005`: Results SHALL state that a single 2D photo gives an estimate.

## 5. Assumptions

- The marker lies in about the same plane as the wound.
- The owner photographs the validation set, using known-size objects and no patient data.

## 6. Dependencies

- `P03-S03`
- `P08-S02`

## 7. Inputs

- Image from the pipeline
- `configs/measurement/marker_v1.json`

## 8. Outputs

- Marker module
- Printable PDF
- Validation report

## 9. Data / Interface Contract

`Calibration(pixels_per_mm, method, source, uncertainty_pct)` feeds the measurement engine unchanged, and `calibration_state` stays `PIXEL_BASED` or `PHYSICALLY_CALIBRATED`. The marker reading (status, corners, side lengths, config version) is stored in `measurement.provenance.marker`. Reason codes: `MARKER_FOUND`, `MARKER_NOT_FOUND`, `MARKER_WRONG_ID`, `MARKER_PARTIAL`, `MARKER_TOO_SMALL`, `MARKER_TILTED`, `MARKER_AMBIGUOUS`, and `SCALE_CONFLICT` when a typed scale disagrees with the marker by more than `conflict_tolerance_pct`.

## 10. Invariants

- No scale is ever invented.
- The source of each scale is stored.
- Trends do not mix pixel and calibrated values.

## 11. Technical Design

Detect with `cv2.aruco`, then average the four side lengths for scale. Reject on low side-length agreement, which signals tilt. Tilt limits come from the validation set, not from guesses.

## 12. Implementation Tasks

1. Add detection and the fallbacks.
2. Create the marker sheet.
3. Collect the validation photos.
4. Measure error and fix limits.
5. Connect to the UI.

## 13. Failure Modes / Edge Cases

| Case | Required behaviour |
|---|---|
| Glare on the marker | Fallback with reason code |
| Several markers | Use the agreed ID; a conflict falls back |
| Marker off the wound plane | Not detectable; documented as a limitation |

## 14. Tests

- Synthetic marker renders with known scale
- Fallback cases
- Real-photo validation

## 15. Acceptance Criteria

- The validation report states error by distance and angle.
- Every failure case falls back to pixels.

## 16. Evidence

Recorded on 2026-11-05.

- `python -m pytest tests/measurement/test_marker.py -q`: 18 passed. They cover the true scale at 2, 3.5 and 5 px/mm,
  10° tilt with noise within 5%, every fallback code, an ambiguous double marker, the conflict rule, the pipeline end
  to end (marker wins, conflict flagged; tilted marker falls back to pixels with its reason), a disabled or bad config,
  the limitation text and the validation script's manifest mode.
- The regression run over `tests/measurement`, `api`, `worker`, `integration`, `release`, `longitudinal` and
  `security` passed.
- `docs/measurement/marker_sheet_v1.pdf` (also served as `web/public/marker-sheet-v1.pdf`): A4 at 300 dpi, 40 mm marker
  and a 50 mm check square. Detected on its own render at 11.797 px/mm against a true 11.811.
- `reports/final/p09_s01_marker_validation_synthetic.json` — **synthetic, not REQ-003 evidence**: 48 pinhole renders,
  36 accepted, median absolute error 0.83%.

  | Tilt | Accepted | Median abs error | Max abs error |
  |---|---|---|---|
  | 0° | 12/12 | 0.07% | 0.11% |
  | 10° | 12/12 | 0.83% | 1.15% |
  | 20° | 12/12 | 3.11% | 3.31% |
  | 30° | 0/12 (`MARKER_TILTED`) | — | — |

  The error at 20° comes from perspective: the marker and the object sit at different depths on a tilted sheet. Real
  photos will decide whether the tilt limits need tightening.
- Web: `tsc`, 25 unit tests, the wording check and the 45-test Playwright pages suite pass. `npx impeccable detect` is
  clean on `/analyses/a1d04e` and `/analyse`, and neither page scrolls sideways at 375 px.

## 17. Reproducibility

```bash
python -m pytest tests/measurement/test_marker.py -q
python scripts/measurement/make_marker_sheet.py
python scripts/evaluation/run_marker_validation.py --synthetic
python scripts/evaluation/run_marker_validation.py --data <photos>/manifest.json   # needs real photos
```

The manifest format is documented at the top of `scripts/evaluation/run_marker_validation.py`. Photograph a printed
sheet beside an object of known length (a ruler or a coin) at several distances and angles, and mark the object's end
points by hand.

## 18. Risks / Limitations

- Printers scale pages, so the sheet includes a check square and the upload form says to measure it.
- Foot curvature remains uncorrected, so wounds on curved surfaces may be mismeasured.
- The tilt limits (`max_side_ratio` 1.15, `max_corner_deviation_deg` 12) are set from synthetic renders, not from the
  real validation set the technical design asks for.
- A marker off the wound plane gives a wrong scale that the detector cannot see. This is stated as a limitation.

## 19. Traceability

| Requirement | Implementation | Test | Evidence | Status |
|---|---|---|---|---|
| `REQ-P09-S01-001` | `src/measurement/marker.py`, `configs/measurement/marker_v1.json` | `test_a_facing_marker_gives_the_true_scale` | Test run 2026-11-05 | COMPLETED |
| `REQ-P09-S01-002` | `src/measurement/marker.py`, `src/measurement/calibration.py` | `test_an_unusable_marker_gives_a_reason_and_no_scale`, `test_the_pipeline_falls_back_to_pixels_with_the_reason` | Test run 2026-11-05 | COMPLETED |
| `REQ-P09-S01-003` | `scripts/evaluation/run_marker_validation.py` | `test_the_validation_script_reads_a_manifest_of_photos` | `reports/final/p09_s01_marker_validation.json` (not yet produced) | BLOCKED: needs real marker photos; synthetic run only |
| `REQ-P09-S01-004` | `src/measurement/calibration.py`, `web/components/Measurements.tsx` | `test_the_marker_wins_and_a_disagreeing_user_scale_is_flagged` | Test run 2026-11-05 | COMPLETED |
| `REQ-P09-S01-005` | `LIMITATION` in `src/measurement/engine.py`, `web/components/Measurements.tsx` | `test_results_say_a_single_photo_gives_an_estimate` | Test run 2026-11-05 | COMPLETED |
