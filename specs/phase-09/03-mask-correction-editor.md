# P09-S03 — Mask Correction Editor

**Status:** `NOT_STARTED`. Nothing in this specification is implemented. It needs approval before work begins.

## 1. Objective

Let users correct a predicted mask and keep both versions, so that measurements improve and corrections can inform later training.

## 2. Scope

- Canvas brush, eraser and undo
- Stored correction linked to the original analysis
- Measurements recomputed from the corrected mask
- Opt-in export of corrections for research

## 3. Non-Goals

- Automatic retraining
- Polygon or AI-assisted annotation tools
- Replacing the original model output

## 4. Requirements

- `REQ-P09-S03-001`: The editor SHALL support brush, eraser, size control, undo and redo, on touch and mouse.
- `REQ-P09-S03-002`: A correction SHALL create a new versioned record and SHALL NOT change the original analysis.
- `REQ-P09-S03-003`: Measurements SHALL be recomputed on the server through the existing engine.
- `REQ-P09-S03-004`: Records and trends SHALL show whether a value comes from a corrected mask.
- `REQ-P09-S03-005`: A correction SHALL be used for research export only after explicit opt-in.

## 5. Assumptions

- Users are not qualified annotators by default, so corrections are not ground truth.

## 6. Dependencies

- `P08-S02`
- `P03-S03`
- `P07-S02`

## 7. Inputs

- Original image and mask
- Edited mask as a PNG

## 8. Outputs

- `mask_corrections` table
- Editor
- Correction API

## 9. Data / Interface Contract

`POST /api/v2/analyses/{id}/corrections` takes a PNG the same size as the image, and returns a correction ID and new measurements. Values must be 0 or 255.

## 10. Invariants

- The model's original output stays available.
- A correction records its author and time.
- Corrections never feed training without review.

## 11. Technical Design

Edit at the display size on a canvas layer, then map to the original size on export. Undo keeps a bounded history of strokes. The server validates dimensions and pixel values before use.

## 12. Implementation Tasks

1. Add the table and API.
2. Build the editor.
3. Connect measurements and trends.
4. Add opt-in and export.

## 13. Failure Modes / Edge Cases

| Case | Required behaviour |
|---|---|
| Wrong dimensions | `INVALID_INPUT` |
| Empty mask submitted | Accepted, with measurements marked empty |
| Connection lost while editing | Local draft is restored |

## 14. Tests

- Immutability
- Editing on touch and mouse
- Size mapping accuracy

## 15. Acceptance Criteria

- An edited mask gives new measurements while the original stays intact.

## 16. Evidence

- Playwright report
- API test report

## 17. Reproducibility

Planned commands. These do not work until the specification is implemented.

```bash
python -m pytest tests/api/test_corrections.py -q
cd web && npx playwright test e2e/editor.spec.ts
```

## 18. Risks / Limitations

- Low-quality corrections could damage later training, so they stay separate from ground truth.

## 19. Traceability

| Requirement | Planned implementation | Planned test | Planned evidence | Status |
|---|---|---|---|---|
| `REQ-P09-S03-001` | `web/components/MaskEditor/` | Playwright test | Test report | NOT_STARTED |
| `REQ-P09-S03-002` | `src/api/corrections.py` | `test_original_is_immutable` | Test run | NOT_STARTED |
| `REQ-P09-S03-003` | `src/api/corrections.py` | `test_measurements_from_corrected_mask` | Test run | NOT_STARTED |
| `REQ-P09-S03-004` | `src/longitudinal/` | `test_trend_marks_corrected` | Test run | NOT_STARTED |
| `REQ-P09-S03-005` | `src/api/corrections.py` | `test_export_requires_opt_in` | Test run | NOT_STARTED |
