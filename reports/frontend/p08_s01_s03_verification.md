# Phase 08 S01 to S03: verification record

Run on 2026-11-04, Windows 11, Node 22, Next 15.5.9, on branch `phase-07-production-platform`, before any commit of this work. Nothing has been pushed, so no CI run exists yet.

## Local checks

| Check | Command (from `web/`) | Result |
|---|---|---|
| Types | `npx tsc --noEmit` | 0 errors |
| Unit tests | `npm test` | 4 files, 24 tests passed (`lib/errors`, `lib/format`, `lib/upload`, `middleware`) |
| Wording | `npm run test:wording` | Passed |
| Client freshness | `npm run api:check` | Exit 0. See the limitation below |
| Pages, mock build | `npx playwright test --project=pages` | 43 passed: 20 routes at 1280 and 375 px, each with the notice, no sideways scroll and no axe WCAG 2.1 A/AA violation, plus 3 trend and comparison checks |
| Design detection, mock build | `npx impeccable detect http://localhost:3002<route>` on `/`, `/cases`, `/analyse`, `/analyses/a1d093`, `/cases/c-0007/trend`, `/compare` | Clean, after fixing the compare slider's stacked placeholder labels |
| Workflow, live stack | `DFU_E2E_BASE_URL=http://localhost:3200 npx playwright test --project=workflow` | 1 passed (4.3 s) |

## The live stack for the workflow test

All local and disposable:

- OIDC: `node e2e/oidc.mjs` (oauth2-mock-server on 8085).
- Redis 3.0.504 on 6390.
- API: `python -m uvicorn src.api.app:app --port 8010` with `DFU_AUTH_ISSUER=http://localhost:8085`, `DFU_AUTH_AUDIENCE=dfu-api`, `DFU_AUTH_JWKS_URL=http://localhost:8085/jwks`, `DFU_REDIS_URL=redis://127.0.0.1:6390` and a scratch `DFU_DATA_DIR`. Readiness reported model, database, storage and queue as ready, with model `spec-02-03-resnet34-unet-512-v1`.
- Worker: `python -m arq src.worker.settings.WorkerSettings` against the same data directory and Redis.
- Web: `NEXT_PUBLIC_DFU_MOCK=0 npx next build`, then `next start -p 3200`, with the `AUTH_OIDC_*`, `NEXTAUTH_*` and `DFU_API_URL` variables from `web/.env.example`.

The test signs in, creates a case, uploads a photo drawn on a canvas in the browser (no real image), polls the result page until the worker finishes, and deletes the case. The worker refused every constructed photo with `QUALITY_REJECTED`, so the live run proved the refusal path. The measured result page, provenance and the trend were checked against the mock layer only.

## Problems found and fixed during verification

- The root `.gitignore` ignores every `lib/` folder (a Python template rule). `web/lib/` had never been tracked, including in commit `a429c36`, so a clean checkout would not build. `web/.gitignore` now re-includes `/lib/`.
- Playwright's mock-build web server ran for the workflow project too, and rebuilt `.next` under the live server. It now runs only when `DFU_E2E_BASE_URL` is unset.
- The workflow test waited for `/cases/new`, which matches the case-page pattern, and typed `delete` where the dialog asks for the case identifier. Both are fixed.

## Limitations

- `api:check` compares against the committed `openapi.json` and `lib/api/schema.d.ts`. Until those files are committed, `git diff` has nothing to compare and the check cannot fail.
- CI runs the pages suite only. The workflow test needs the stack above and is not in CI.
- No screen recording was made. No preview deployment exists, because deployment belongs to the owner.
