# P08-S01 — Next.js Frontend Foundation

**Status:** `IN_PROGRESS`. Code and local tests are done and pass. The CI job has not run because nothing is pushed, and the client-freshness check only bites once `openapi.json` and `lib/api/schema.d.ts` are committed.

## 1. Objective

Create the web application shell that every later screen builds on.

## 2. Scope

- Next.js with TypeScript, Tailwind and shadcn/ui in `web/`
- Sign-in pages from the auth provider
- Typed API client generated from the OpenAPI schema
- Layout, navigation and error pages
- Medical notice on every page
- Frontend CI

## 3. Non-Goals

- Analysis or case screens, which belong to P08-S02
- Mobile applications
- Server-side model calls

## 4. Requirements

- `REQ-P08-S01-001`: The API client SHALL be generated from the service's OpenAPI schema, and CI SHALL fail when it is out of date.
- `REQ-P08-S01-002`: Every page SHALL show the not-a-medical-device notice, from a shared layout.
- `REQ-P08-S01-003`: Signed-out users SHALL reach only public pages.
- `REQ-P08-S01-004`: Every API error category SHALL have a defined user message that keeps quality rejection distinct from system failure.
- `REQ-P08-S01-005`: Core pages SHALL pass automated accessibility checks at WCAG 2.1 AA and work at 375 px width.

## 5. Assumptions

- The frontend deploys to Vercel; the API stays a separate service.
- `web/` holds the whole frontend, so Python and Node tooling stay apart.

## 6. Dependencies

- `P07-S04`

## 7. Inputs

- OpenAPI schema at `/openapi.json`
- Auth provider keys

## 8. Outputs

- `web/` application
- Frontend CI job
- Vercel project

## 9. Data / Interface Contract

The frontend talks only to `/api/v2`, with the user's bearer token. It never sees storage credentials. `NEXT_PUBLIC_API_URL` selects the API.

## 10. Invariants

- The frontend never calls model code.
- No diagnostic wording appears in any string.
- The UI labels results as image-derived technical measurements.

## 11. Technical Design

App Router with server components for public pages and client components for interactive screens. TanStack Query handles fetching and caching. `openapi-typescript` generates types, so a contract change breaks the build instead of the user.

## 12. Implementation Tasks

1. Scaffold `web/`.
2. Add auth pages and route protection.
3. Generate the client and add the CI check.
4. Build the layout, notice and error pages.
5. Add Playwright and axe.

## 13. Failure Modes / Edge Cases

| Case | Required behaviour |
|---|---|
| API unreachable | A clear service-unavailable page, with no fake data |
| Session expires | Redirect to sign-in and return to the same page |
| Schema drift | CI fails |

## 14. Tests

- Playwright route checks
- Accessibility checks
- Error-mapping unit test

## 15. Acceptance Criteria

- A user can sign in, see an empty workspace and sign out on desktop and phone widths.
- CI blocks a stale client.

## 16. Evidence

- `reports/frontend/p08_s01_s03_verification.md`
- Playwright output, `npx playwright test --project=pages`: 43 passed
- No preview deployment: deployment belongs to the owner

## 17. Reproducibility

```bash
cd web && npm ci && npx tsc --noEmit && npm test && npm run api:check && npx playwright test --project=pages
```

## 18. Risks / Limitations

- Framework churn; versions are pinned by the lockfile.
- A second language adds maintenance cost.

## 19. Traceability

| Requirement | Implementation | Test | Evidence | Status |
|---|---|---|---|---|
| `REQ-P08-S01-001` | `web/lib/api/`, `web/scripts/export_openapi.py` | `npm run api:check` in the CI `web` job | Local exit 0; no CI log yet | IN_PROGRESS |
| `REQ-P08-S01-002` | `web/components/MedicalNotice.tsx` in both layouts | `e2e/pages.spec.ts`, 20 routes at two widths | `reports/frontend/p08_s01_s03_verification.md` | COMPLETED |
| `REQ-P08-S01-003` | `web/middleware.ts` | `middleware.test.ts` | `reports/frontend/p08_s01_s03_verification.md` | COMPLETED |
| `REQ-P08-S01-004` | `web/lib/errors.ts`, `web/components/ErrorPanel.tsx` | `lib/errors.test.ts` | `reports/frontend/p08_s01_s03_verification.md` | COMPLETED |
| `REQ-P08-S01-005` | `web/app/` layouts | `e2e/pages.spec.ts`: axe WCAG 2.1 A/AA and overflow at 375 px | `reports/frontend/p08_s01_s03_verification.md` | COMPLETED |