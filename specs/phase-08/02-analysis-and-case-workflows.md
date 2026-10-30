# P08-S02 — Analysis and Case Workflows

**Status:** `NOT_STARTED`. Nothing in this specification is implemented. It needs approval before work begins.

## 1. Objective

Let a user create a case, upload a photo, follow the analysis and read the result in the browser.

## 2. Scope

- Case and examination pages
- Drag-and-drop upload through pre-signed URLs
- Progress view for queued jobs
- Result page with overlay, measurements, quality status and provenance
- Sample images for trying the system without an upload

## 3. Non-Goals

- Trend charts, which belong to P08-S03
- Mask editing, which belongs to P09-S03
- Batch upload

## 4. Requirements

- `REQ-P08-S02-001`: The upload SHALL validate type and size in the browser and again on the server, and SHALL show consent text before the first upload.
- `REQ-P08-S02-002`: The result page SHALL poll job status and show each state, including retry after failure.
- `REQ-P08-S02-003`: A quality rejection SHALL show its reason codes in plain language and guidance for retaking the photo.
- `REQ-P08-S02-004`: Measurements SHALL show their unit and calibration state. Pixel values SHALL NOT be displayed as millimetres.
- `REQ-P08-S02-005`: Results SHALL show model version and the external-validation limitation.
- `REQ-P08-S02-006`: A full end-to-end test SHALL cover sign-in, case creation, upload, result and deletion against a real API and worker.

## 5. Assumptions

- Sample images must be licensed for redistribution, or be synthetic. FUSeg images are not assumed to be redistributable.
- Polling at 1–2 s intervals is enough; server-sent events can follow if P10-S02 shows the need.

## 6. Dependencies

- `P08-S01`
- `P07-S03`
- `P07-S05`

## 7. Inputs

- `/api/v2` routes

## 8. Outputs

- Case, upload and result screens
- End-to-end test suite

## 9. Data / Interface Contract

The flow is `POST /api/v2/uploads`, PUT to storage, `POST /api/v2/analyses`, then `GET /api/v2/analyses/{id}` until the state is final.

## 10. Invariants

- An image is uploaded only after consent.
- A failed analysis never shows measurements.
- Every result shows its calibration state.

## 11. Technical Design

The overlay view uses the original image with the mask drawn on a canvas layer and an opacity control. Polling stops at a final state and backs off when the tab is hidden.

## 12. Implementation Tasks

1. Build case and examination pages.
2. Build the upload component.
3. Build the progress and result pages.
4. Add sample images.
5. Add the end-to-end suite.

## 13. Failure Modes / Edge Cases

| Case | Required behaviour |
|---|---|
| Upload interrupted | Offer retry; the unfinished row expires |
| Job failed | Show the failure class and a retry action |
| Quality rejected | Show reasons, with no measurement |
| Large image on a slow phone | Show upload progress |

## 14. Tests

- Component tests per state
- End-to-end flow
- Phone-width checks

## 15. Acceptance Criteria

- A new user finishes the sample flow without instructions.
- The end-to-end suite passes in CI.

## 16. Evidence

- Playwright report
- Screen recording of the flow

## 17. Reproducibility

Planned commands. These do not work until the specification is implemented.

```bash
cd web && npx playwright test e2e/
```

## 18. Risks / Limitations

- Dataset licences limit which samples can ship.
- CI needs a small model for the end-to-end run, so that test proves the flow and not model quality.

## 19. Traceability

| Requirement | Planned implementation | Planned test | Planned evidence | Status |
|---|---|---|---|---|
| `REQ-P08-S02-001` | `web/components/Upload.tsx` | Playwright upload test | Test report | NOT_STARTED |
| `REQ-P08-S02-002` | `web/app/analyses/[id]/` | Playwright with mocked states | Test report | NOT_STARTED |
| `REQ-P08-S02-003` | `web/components/QualityResult.tsx` | Component test | Test report | NOT_STARTED |
| `REQ-P08-S02-004` | `web/components/Measurements.tsx` | Component test | Test report | NOT_STARTED |
| `REQ-P08-S02-005` | `web/components/Provenance.tsx` | Playwright check | Test report | NOT_STARTED |
| `REQ-P08-S02-006` | `web/e2e/` | Playwright in CI | Test report | NOT_STARTED |
