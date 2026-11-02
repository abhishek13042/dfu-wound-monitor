# P08-S04 — Design System and Screen Specification

**Status:** `IN_PROGRESS`. The screens exist in `web/` against a mock layer. They are not wired to `/api/v2`, and the acceptance criteria in section 15 are not all met. The direction ran without a user review round, so it still needs approval.

## 1. Objective

Define how every page of the web application looks and behaves, so that P08-S01, P08-S02 and P08-S03 build one product instead of three.

## 2. Scope

- Visual system: colour, type, spacing, shape and motion tokens
- The reading strip, which is the product's signature component
- Screen specifications for all public and app pages
- State specifications for every analysis status and error category
- A labelled mock layer shaped like `/api/v2`

## 3. Non-Goals

- API, database, auth provider or deployment work
- Phase 09 screens: marker calibration, probability heatmap, mask editor
- Replacing `src/dashboard/index.html`, which stays for `/api/v1`
- A dark theme. The use scene does not call for one (section 11.2)

## 4. Requirements

### Visual system

- **REQ-P08-S04-001:** All colour, type, spacing and shape values come from the tokens in `web/app/globals.css`. Components hold no literal colours.
- **REQ-P08-S04-002:** Body text meets 4.5:1 contrast and large text meets 3:1, including text on the aubergine rail.
- **REQ-P08-S04-003:** Numeric values use tabular figures and always appear with a unit, a measurement basis and a model version.

### Reading strip

- **REQ-P08-S04-004:** The strip shows nine pads in a fixed order: decode, size, aspect, content, sharpness, underexposure, overexposure, contrast, glare.
- **REQ-P08-S04-005:** Each pad encodes pass, fail and not-read through a drawn mark as well as colour. Failed pads are named in text next to the strip.
- **REQ-P08-S04-006:** The strip has compact, standard and key sizes, and all three expose the same text to assistive technology.
- **REQ-P08-S04-007:** Pads resolve in sequence with hard steps and no easing. With reduced motion they appear resolved at once.

### Screens

- **REQ-P08-S04-008:** Every page in section 9 is built and reachable, and renders at 1440 px and 375 px with no horizontal page scroll.
- **REQ-P08-S04-009:** The notice "Research prototype. Not a medical device." appears on every page, from a shared layout.
- **REQ-P08-S04-010:** Pooled Dice 0.92 and 0.26 appear at equal type size and weight wherever either appears.
- **REQ-P08-S04-011:** The five analysis statuses and nine error categories each have a distinct title, explanation and next action.
- **REQ-P08-S04-012:** A rejected analysis has its own page state with the failed pads, the plain-language reason and retake guidance. It shows no measurement.
- **REQ-P08-S04-013:** Pixel and calibrated values never share a chart axis, the trend chart has a true-spaced time axis, and excluded examinations are listed with reasons.
- **REQ-P08-S04-014:** Comparison states that two photos are not claimed to be aligned.
- **REQ-P08-S04-015:** The mask overlay has a visible opacity control and is the only translucent layer in the product.
- **REQ-P08-S04-016:** The landing page shows no wound photograph. Public wound images appear only by user intent.

### Mock layer

- **REQ-P08-S04-017:** All screens read data through one module, `web/lib/api/`, with types matching `/api/v2`, so the mock can be replaced without touching components.
- **REQ-P08-S04-018:** Mock data is labelled on screen as constructed, on every page that shows it.
- **REQ-P08-S04-019:** No string uses diagnostic wording: heal, healing, deteriorat, improving, worsening, treatment response, prognosis, or a clinical recommendation. The fixed limitation statements that deny these claims are the only exception.

## 5. Assumptions

- The direction recorded in `.impeccable/surfaces/web-app.md` holds until the user reviews it.
- One image has at most one analysis result on screen at a time.
- The quality response carries the measures and thresholds defined in `src/quality/gate.py`. `src/api/schemas.py` types it only as a dictionary, so the pad mapping must be checked against a live response.

## 6. Dependencies

- `P08-S01`, `P08-S02`, `P08-S03` for behaviour
- `P07-S04` for sign-in, which is mocked until a provider is chosen
- `PRODUCT.md` for product truth

## 7. Inputs

`/api/v2` responses as described in `docs/api/API.md`, replaced for now by constructed data in `web/lib/api/mock-data.ts`.

## 8. Outputs

- The `web/` application
- `DESIGN.md` and `.impeccable/design.json`, recorded from the finished build
- This specification

## 9. Data / Interface Contract

### 9.1 Page map

| Route | Mode | Purpose | Key states |
|---|---|---|---|
| `/` | Persuade | The key chart, mechanism and evidence | Signed out |
| `/model` | Read | Model card, both results, failure modes | Public |
| `/sign-in` | Operate | Provider hand-off placeholder | Provider not chosen |
| `/cases` | Operate | All cases with latest reading | Empty, filtered empty, list |
| `/cases/new` | Operate | Create a case with identity status | Validation |
| `/cases/[id]` | Operate | Timeline of examinations, delete case | No examinations, list, delete confirmation |
| `/cases/[id]/trend` | Operate | Trend chart, table and exclusions | Unavailable, pixel, calibrated |
| `/analyse` | Operate | Consent, photo, capture details, calibration | Consent, invalid file, ready, uploading |
| `/analyses/[id]` | Operate | Progress, result or rejection | All five statuses |
| `/compare` | Operate | Two analyses with compatibility | Compatible, incompatible |
| `/account` | Operate | Export data, delete account | Delete confirmation |
| `not-found`, `error` | Operate | Named failure pages | Static |

### 9.2 Shared layouts

- **Public layout:** header with name, Model evidence and Sign in; footer with the notice and limitation.
- **App layout:** 220 px aubergine rail at desktop, top bar with a menu below 900 px. The rail holds Cases, New analysis, Compare, Account, and the service readiness of model, database, storage and queue.
- **Notice:** one component in both layouts, always in view at the top of the page.

### 9.3 Reading strip mapping

| Pad | Source measure | Reason code |
|---|---|---|
| Decode | file opened | `UNREADABLE` |
| Size | shortest side, minimum 128 px | `TOO_SMALL` |
| Aspect | ratio, maximum 4.0 | `BAD_ASPECT_RATIO` |
| Content | content fraction, entropy | `INSUFFICIENT_CONTENT` |
| Sharpness | Laplacian variance, minimum 8 | `BLURRY` |
| Underexposure | mean luminance, dark fraction | `UNDEREXPOSED` |
| Overexposure | mean luminance, bright fraction | `OVEREXPOSED` |
| Contrast | luminance deviation, minimum 10 | `LOW_CONTRAST` |
| Glare | glare fraction, maximum 0.40 | `GLARE` |

## 10. Invariants

- A failed pad never appears beside a measurement.
- Table columns keep their position in every state; only cell contents change.
- A row whose state changed stays marked until it is opened.
- The client never recomputes a trend value.

## 11. Technical Design

### 11.1 World

The reference colour key printed on a reagent bottle label. It lends type, palette, density and the strip. Navigation, forms and tables stay standard web controls.

### 11.2 Colour

Used under daylight or clinic light, on a phone or tablet at the bedside and on a laptop at a desk, so the product is light. The rail and public hero are aubergine, the ground is pale reagent green, and panels are white. Reading colours do fixed jobs: pad green for pass, oxide for quality rejection, magenta for system failure, mustard for warnings, slate blue for calibrated series. Failure classes never share a colour.

### 11.3 Type

Archivo for interface and display, using its width axis for condensed headings. Spline Sans Mono for values, codes and IDs. Scale: 12, 13, 14, 16, 20, 28, 40, 72 px.

### 11.4 Shape, density and motion

Corners are 2 px. Depth comes from hairlines; only menus and dialogs carry a soft shadow. Table rows are 44 px, which also meets the touch target. Motion is limited to the pad sequence, in steps of 90 ms.

### 11.5 Research source

Patterns taken from sites opened for this work:

| Pattern | Source |
|---|---|
| Image series beside measurements | nethealth.com/tissue-analytics |
| Capture, manage and review as named stages | swiftmedical.com |
| Permanent "investigational use" statement on the working surface | viewer.ohif.org |
| Model facts in a side column beside the long card | huggingface.co model card |

Outcome statistics and "heal faster" claims on the first two sites are the anti-pattern here. This product claims no outcome.

## 12. Implementation Tasks

- [x] Record the direction and write this specification
- [x] Scaffold `web/` and tokens
- [x] Build shared layouts, strip and mock layer
- [x] Build all pages in section 9.1
- [x] Verify at desktop and mobile, run detection, audit and polish
- [x] Finish review and its eight fixes
- [x] `DESIGN.md` recorded from the build
- [ ] Replace the mock layer with the generated client (P08-S01)

## 13. Failure Modes / Edge Cases

| Case | Behaviour |
|---|---|
| Fewer than two trend points | Chart replaced by a statement of why |
| Long case label | Truncated in tables, full on the case page |
| All nine pads failed | Strip stays one line; reasons stack below |
| Unreadable file | Decode fails, other pads show not read |
| Mixed bases in one case | Separate series and axes, never merged |
| `BUSY` | Retry-After time shown, action disabled until it passes |

## 14. Tests

- `npm run build` type-checks all routes
- `npm run test:wording` scans source for forbidden wording
- `impeccable detect` on running pages
- Playwright and axe arrive with P08-S01

## 15. Acceptance Criteria

- [ ] All REQ-P08-S04 items pass on the running app
- [x] Detection reports no unresolved finding
- [x] Finish review returns ship
- [x] `DESIGN.md` matches the build
- [ ] User approves the direction

## 16. Evidence

These checks ran on the production build (`npm run build`, served on port 3002). They do not cover physical touch, screen readers, 200% text zoom, Firefox or Safari, so REQ-P08-S04 is not claimed as passing.

- `npm run build` passed, including its type check, and generated every route.
- A scripted capture of 23 routes and states at 1440 and 375 px reported no overflow or clipping. A second script checked five routes at 768 px and the cases table at 1024 px, with no overflow, and confirmed the keyboard focus order.
- A contrast check on 15 routes found no text below WCAG AA.
- `impeccable detect` returned no findings on `/`, `/cases`, `/analyses/a1d093` and `/analyses/a1d066`. The small-target hits it reported earlier were hidden inputs and are listed as false positives in the audit.
- The audit scored 15 of 20. Every P1 and P2 finding was fixed. See `.impeccable/review/audit.md`.
- The finish review asked for eight fixes, listed in the audit. Two of them caused regressions in the cases table, a split header and truncated labels at 768 px, which were then fixed. On recapture the reviewer returned ship. That covers the fixes and regressions, not a fresh review of every screen.
- `DESIGN.md` and `.impeccable/design.json` were written from the shipped code. The documenter reported pass-green hover fills on table rows and the upload area. They now use the neutral `secondary` fill, and detect stays clean on five routes. Other leftover shadcn styles it listed, such as select popup easing and some focus rings in unused variants, are not recorded as rules and remain open.
- Captures of the final build are in `.impeccable/review/`. They were taken with reduced motion, because headless Chrome does not advance the pad entrance animation.

The mock layer accepts `?error=` on `/analyse` and `?state=empty` on `/cases` to preview those states. Both leave with the mock layer.

## 17. Reproducibility

```bash
cd web
npm install
npm run dev
```

## 18. Risks / Limitations

- The direction has not been reviewed by the user.
- Screens were designed against constructed data only.
- The pad mapping is inferred from `src/quality/gate.py`, not from a live `/api/v2` response.
- The retention period is shown as a placeholder until it is decided.

## 19. Traceability

Requirements trace to `specs/TRACEABILITY.md`. Behaviour requirements stay in P08-S01 to P08-S03; this specification owns only their visual form.
