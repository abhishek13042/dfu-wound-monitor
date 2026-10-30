# P09-S01 — Reference-Marker Calibration

**Status:** `NOT_STARTED`. Nothing in this specification is implemented. It needs approval before work begins.

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

`Calibration(method, pixels_per_mm, source, confidence)` feeds the measurement engine unchanged, and `calibration_state` stays `PIXEL_BASED` or `PHYSICALLY_CALIBRATED`.

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

- `reports/final/p09_s01_marker_validation.json`

## 17. Reproducibility

Planned commands. These do not work until the specification is implemented.

```bash
python scripts/evaluation/run_marker_validation.py --data <photos>
```

## 18. Risks / Limitations

- Printers scale pages, so the sheet includes a check square.
- Foot curvature remains uncorrected, so wounds on curved surfaces may be mismeasured.

## 19. Traceability

| Requirement | Planned implementation | Planned test | Planned evidence | Status |
|---|---|---|---|---|
| `REQ-P09-S01-001` | `src/measurement/marker.py` | `tests/measurement/test_marker.py` | Test run | NOT_STARTED |
| `REQ-P09-S01-002` | `src/measurement/marker.py` | `test_marker_fallbacks` | Test run | NOT_STARTED |
| `REQ-P09-S01-003` | `scripts/evaluation/run_marker_validation.py` | Validation run | `reports/final/p09_s01_marker_validation.json` | NOT_STARTED |
| `REQ-P09-S01-004` | `src/measurement/calibration.py` | `test_scale_conflict` | Test run | NOT_STARTED |
| `REQ-P09-S01-005` | API limitation text | `test_limitation_present` | Test run | NOT_STARTED |
