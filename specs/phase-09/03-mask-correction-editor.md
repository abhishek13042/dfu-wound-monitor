# P09-S03 — Mask Correction Editor

**Status:** `COMPLETED`. All five requirements are built and tested against the API and the constructed-data web build. See §16 for what was and was not run.

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
- The author of a correction is the signed-in owner of the analysis; there is no shared editing.
- Trends use the latest correction of each analysis. Earlier versions stay listed and downloadable.

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

`POST /api/v2/analyses/{id}/corrections` takes multipart `file` (a PNG the same size as the image) and optional `research_opt_in` (default false). It returns 201 with `correction_id`, `version`, `author`, `created_at`, `sha256`, `measurement`, `research_opt_in` and `links`. Values must be 0 or 255; grey, grey with alpha, RGB and RGBA are accepted when every pixel is black or white and opaque, because a browser canvas only writes RGBA.

| Route | Purpose |
|---|---|
| `GET /api/v2/analyses/{id}/corrections` | Every version, oldest first |
| `GET /api/v2/corrections/{id}/mask` | Signed URL for the stored mask |
| `PUT /api/v2/corrections/{id}/research` | `{"opt_in": bool}` |

Errors: `MASK_NOT_PNG`, `MASK_SIZE_MISMATCH`, `MASK_NOT_GRAYSCALE`, `MASK_VALUES` (400, `INVALID_INPUT`), `MASK_TOO_LARGE` (413), `ANALYSIS_NOT_COMPLETED` (409). Trend rows gain `mask_source` (`MODEL` or `CORRECTED`) and `correction_id`. The account export gains `corrections`.

## 10. Invariants

- The model's original output stays available.
- A correction records its author and time.
- Corrections never feed training without review.

## 11. Technical Design

The canvas is the photo's own size (for example 1600 × 1200) and is scaled for display, so pointer positions are mapped to image pixels through `getBoundingClientRect` and nothing is resampled on export. Pointer events cover mouse, pen and touch; the canvas sets `touch-action: none` and captures the pointer. Each stroke end snaps the edge to on or off, so what is drawn is what is saved.

Undo keeps up to 20 snapshots of one byte per pixel (under 40 MB at 1600 × 1200). The draft is a PNG in `localStorage` under `dfu-mask-draft:<analysis_id>`, written when each stroke ends and offered for restore on the next visit. Saving exports an opaque 0/255 PNG.

The server checks the PNG size from its header before decoding, then the values, measures with `src.measurement.engine.measure` and the analysis's own calibration, and stores the mask in canonical form in blob storage (`mask_corrections`, migration 0006). The measurement drops the missing-model-score warning and adds `CORRECTED_MASK`. The trend route swaps in a copy of the analysis carrying the latest correction's measurement; the stored analysis is never written. Correction blobs go with the case on delete, retention and the account export. `scripts/data/export_corrections.py` writes only opted-in masks, each checked against its hash and marked `UNREVIEWED`.

Web: `web/components/MaskEditor.tsx`, `web/components/Corrections.tsx` on the analysis page, and a "Corrected outline" tag in the trend table and chart tooltip.

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
| Save fails | The error is shown and the draft is kept on the device |
| Mask not black and white, or not opaque | `MASK_NOT_GRAYSCALE` or `MASK_VALUES` |
| Analysis not completed | `ANALYSIS_NOT_COMPLETED` |
| Another user's analysis or correction | 404, as if it did not exist |
| Stored mask cannot be read by the browser (no CORS on the storage host) | The editor starts empty and says so |

## 14. Tests

- Immutability
- Editing on touch and mouse
- Size mapping accuracy

## 15. Acceptance Criteria

- An edited mask gives new measurements while the original stays intact.

## 16. Evidence

Recorded on 2026-11-05.

- **API (REQ-002 to -005):** `tests/api/test_corrections.py`, 10 tests, all passing. They cover immutability of the analysis and its mask, server measurement equal to `measure()` on the same mask, empty masks, each invalid-input code, RGBA and LA canvases, another user getting 404 on all four routes, the trend flag and value, the opt-in research query, the account export, deletion with the case, and the research export script. `tests/api/test_auth.py::test_cross_user_isolation` probes the four new routes.
- **Full Python suite:** 497 passed, 3 skipped (each skip needs a server or a dataset file that is not on this machine).
- **Web (REQ-001, -004):** Playwright `pages` project against constructed data, 51 tests passing, including:
  - the analysis page with the editor section at 1280 and 375 px, with axe WCAG 2.1 AA and no sideways scroll;
  - a mouse stroke adds pixels, undo and redo return the exact pixel count, a reload offers the draft and restores it to the same count, axe passes with the editor open, and saving clears the draft;
  - a touch drag through CDP touch events draws, and the page does not scroll under the finger;
  - the trend table marks the corrected row.
- `tsc`, the wording check, Vitest (25 tests) and `impeccable detect` on the analysis and trend pages are clean.
- **Not run:** the editor against the live API in a browser, a physical touch device, and a stored mask served from a storage host without CORS. The save path in the browser was exercised only in constructed-data mode, which sends nothing; the API side of the same request is covered by the tests above.

## 17. Reproducibility

```bash
python -m pytest tests/api/test_corrections.py tests/api/test_auth.py -q
python scripts/data/export_corrections.py --output data/corrections_review
cd web && npx playwright test --project=pages
```

## 18. Risks / Limitations

- Low-quality corrections could damage later training, so they stay separate from ground truth: the research export marks every mask `UNREVIEWED` and nothing reads it for training.
- The editor reads the model's mask from a signed URL. If the storage host does not send CORS headers, the browser cannot read the pixels and the editor starts empty.
- A draft lives in one browser's `localStorage`, so it does not follow the user to another device, and a full quota means no draft.
- Trends use only the latest correction. A user who wants an earlier version must save it again.
- Large photos cost memory: 20 undo steps of a 4000 × 3000 photo are about 240 MB.

## 19. Traceability

| Requirement | Implementation | Test | Evidence | Status |
|---|---|---|---|---|
| `REQ-P09-S03-001` | `web/components/MaskEditor.tsx`, `web/components/Corrections.tsx` | `e2e/pages.spec.ts`: outline editor, finger drag | Playwright run, §16 | COMPLETED |
| `REQ-P09-S03-002` | `src/api/corrections.py`, `src/storage/repository.py` (`mask_corrections`) | `test_original_is_immutable` | Test run, §16 | COMPLETED |
| `REQ-P09-S03-003` | `src/api/corrections.py` (`measure_correction`) | `test_measurements_from_corrected_mask`, `test_empty_mask_is_accepted_and_marked_empty`, `test_bad_masks_are_invalid_input` | Test run, §16 | COMPLETED |
| `REQ-P09-S03-004` | `src/api/resources.py`, `src/longitudinal/trends.py`, trend page, `TrendChart` | `test_trend_marks_corrected`, `e2e/pages.spec.ts`: corrected trend value | Test run, §16 | COMPLETED |
| `REQ-P09-S03-005` | `PUT /corrections/{id}/research`, `scripts/data/export_corrections.py` | `test_export_requires_opt_in`, `test_research_export_holds_only_opted_in_masks` | Test run, §16 | COMPLETED |
