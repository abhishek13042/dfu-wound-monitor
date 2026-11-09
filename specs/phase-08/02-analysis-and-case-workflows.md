# P08-S02 — Analysis and Case Workflows

**Status:** `IN_PROGRESS`. Code is done and the end-to-end test passes on a local stack with the real API, worker, Redis and a local OIDC provider. It is not in CI, and the constructed photo was refused, so the measured path was checked on the mock layer only.

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

- `reports/frontend/p08_s01_s03_verification.md`
- No screen recording was made

## 17. Reproducibility

```bash
cd web && npx playwright test --project=pages
# with the local stack described in the report running:
DFU_E2E_BASE_URL=http://localhost:3200 npx playwright test --project=workflow
```

## 18. Risks / Limitations

- Dataset licences limit which samples can ship.
- CI needs a small model for the end-to-end run, so that test proves the flow and not model quality.

## 19. Traceability

| Requirement | Implementation | Test | Evidence | Status |
|---|---|---|---|---|
| `REQ-P08-S02-001` | `web/components/UploadForm.tsx`, `web/lib/upload.ts`; the server check is the P07 upload verify | `lib/upload.test.ts`; consent step in `e2e/workflow.spec.ts` | `reports/frontend/p08_s01_s03_verification.md` | COMPLETED |
| `REQ-P08-S02-002` | `web/components/AnalysisPoller.tsx`, `web/app/(app)/analyses/[id]/` | `e2e/workflow.spec.ts` waits on the real worker; mock states in `e2e/pages.spec.ts` | `reports/frontend/p08_s01_s03_verification.md` | COMPLETED |
| `REQ-P08-S02-003` | `web/app/(app)/analyses/[id]/`, `web/lib/copy.ts` | Live `QUALITY_REJECTED` result in `e2e/workflow.spec.ts` | `reports/frontend/p08_s01_s03_verification.md` | COMPLETED |
| `REQ-P08-S02-004` | `web/components/Measurements.tsx`, `web/lib/format.ts` | `lib/format.test.ts` | `reports/frontend/p08_s01_s03_verification.md` | COMPLETED |
| `REQ-P08-S02-005` | `web/components/Provenance.tsx` | `e2e/pages.spec.ts` on mock results | `reports/frontend/p08_s01_s03_verification.md`, mock layer only | COMPLETED |
| `REQ-P08-S02-006` | `web/e2e/workflow.spec.ts`, `web/e2e/oidc.mjs` | Local run passed; not in CI | Local run in `reports/frontend/p08_s01_s03_verification.md` | IN_PROGRESS |