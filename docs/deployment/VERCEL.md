# Vercel: the dashboard in demonstration mode (free)

This puts the `web/` dashboard online on Vercel's free Hobby plan. It runs in **mock mode**: every page uses the constructed demonstration data in `web/lib/api/mock.ts`, and a banner on every page says so. It does not call `/api/v2`, does not sign anyone in, and holds no patient data.

The model server cannot run on Vercel: the PyTorch image is about 2 GB, far above the serverless limits. For a demo that runs the model, see the free browser-only Space in `HUGGINGFACE.md`.

## What is already in the repository

| File | What it does |
|---|---|
| `web/vercel.json` | Sets the framework to Next.js, installs with `npm ci` and builds with `npm run build:mock` |
| `web/package.json` | `build:mock` runs `next build` with `NEXT_PUBLIC_DFU_MOCK=1`, which is inlined at build time |
| `web/lib/api/mode.ts` | `isMock` selects the mock data layer |
| `web/middleware.ts` | Skips the sign-in check in mock mode |

No environment variables are needed. `NEXTAUTH_SECRET`, `AUTH_OIDC_*` and `DFU_API_URL` are only read when mock mode is off.

Checked locally on 2026-11-09: `npm run build:mock` passes (14 static pages), and the production server answers 200 on `/`, `/cases`, `/cases/new`, `/cases/<id>`, `/cases/<id>/trend`, `/analyses/<id>`, `/analyse`, `/compare`, `/model`, `/privacy`, `/account` and `/sign-in`, with no browser console errors and no auth variables set. `/api/v2/*` returns 404 in mock mode, as intended.

## Deploy from the Vercel website (no install)

1. Sign in at [vercel.com](https://vercel.com) with GitHub. Choose the **Hobby** plan; it needs no card. Hobby is for personal, non-commercial use.
2. **Add New → Project**, and import `abhishek13042/dfu-wound-monitor`.
3. Set **Root Directory** to `web`. Leave the build and install settings alone; `web/vercel.json` supplies them.
4. Leave **Environment Variables** empty, then **Deploy**.

Vercel builds the repository's production branch, which is `main`. Until PR #1 is merged, `main` has no `web/` mock build; either merge first, or in **Settings → Git** deploy the `phase-07-production-platform` branch as a preview.

## Or deploy from the command line

```bash
npm install -g vercel
```

```bash
cd web
vercel
```

```bash
vercel --prod
```

The first `vercel` run asks you to sign in and link the project; answer that the code is in the current directory (`web`).

## Check the deployment

Open the URL Vercel prints and confirm:

- The yellow notice at the top says the results are constructed demonstration data.
- **Cases** lists the demonstration cases, and a case opens with its trend.
- No sign-in page appears.

## Switching to a real deployment later

Mock mode is fixed by `web/vercel.json`. For a deployment that talks to a real API, change `buildCommand` to `npm run build`, and set `DFU_API_URL`, `NEXTAUTH_URL`, `NEXTAUTH_SECRET` and the `AUTH_OIDC_*` values from `web/.env.example` in the Vercel project settings. That needs a hosted API, which is outside the free plan (see `specs/phase-08/02-analysis-and-case-workflows.md`).
