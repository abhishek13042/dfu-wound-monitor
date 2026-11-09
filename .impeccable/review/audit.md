# Audit, web/ (2026-11-02)

The audit ran against the production build (`next start`, port 3002) and covered all 12 routes plus the preview states. Pages were captured headless in Chrome at 1440, 1024, 768 and 375 px. Contrast was measured on every text node, and focus was checked by pressing Tab through the cases page.

## Health score

| # | Dimension | Score | Key finding |
|---|-----------|-------|-------------|
| 1 | Accessibility | 3 | Focus rings on the shadcn button, select and checkbox were 50% alpha rings. They now use the global 2 px outline. |
| 2 | Performance | 3 | `/cases/[id]/trend` first load is 216 kB, mostly Recharts. No raster images. |
| 3 | Theming | 3 | All colour comes from tokens. The one literal is `themeColor` in `app/layout.tsx`, a meta value. A light-only theme is deliberate. |
| 4 | Responsive | 3 | Tables overlapped on phones, and the cases table truncated labels on tablets. Both are fixed. |
| 5 | Implementation integrity | 3 | The system holds together and belongs to this product. Detector issues are fixed (see below). |
| **Total** | | **15/20** | **Good** |

## Integrity verdict

Pass. The reading strip, the state tags and the failure colours (pass green, oxide rejection, magenta failure) mean the same thing on every page. Measurements always carry a unit, a basis and a model version. The detector reported two issues on rendered pages, a long line on `/model` and a one-word last line on `/`, and both are fixed. All other routes scanned clean.

## Findings

| Sev | Issue | Location | Status |
|---|---|---|---|
| P0 | Stacked table rows kept their fixed 44 px height on phones, so the cells overlapped and could not be read | `CasesTable.tsx`, `cases/[id]/page.tsx`, `trend/page.tsx` | Fixed. The fixed height now applies only when the table is not stacked. |
| P1 | The case label in the cases table was truncated to "Constr…" between 640 and about 1180 px, because the rail narrows the table | `CasesTable.tsx` | Fixed. The table now stacks by its own width (container query, under 820 px) and uses a four-up grid when there is room. |
| P1 | Focus on buttons, the select and the checkbox was a 50%-alpha ring that was hard to see on the aubergine primary button (WCAG 2.4.7) | `components/ui/button.tsx`, `select.tsx`, `checkbox.tsx` | Fixed. They now use the global `:focus-visible` outline. |
| P1 | The "Read the full model card" link was under 24 px tall (WCAG 2.5.8) | `(public)/page.tsx` | Fixed. The target is now at least 44 px tall. |
| P2 | The public header wrapped "DFU-WoundMonitor" and "Sign in" onto two lines at 375 px | `(public)/layout.tsx`, `Wordmark.tsx` | Fixed. The header no longer wraps, and the link reads "Model" on phones. |
| P2 | `/model` paragraphs ran about 94 characters per line | `(public)/model/page.tsx` | Fixed. The paragraphs are now 60ch wide. |
| P3 | One word alone on the last line of a paragraph | `/` | Fixed. `text-wrap: pretty` now applies to `p`, `dd` and `li`. |
| P3 | Field labels inside mono value cells inherited the mono font when stacked | `globals.css` | Fixed |

## Finish review fixes

The finish reviewer asked for eight fixes. All of them were applied, and the app was rebuilt and rechecked.

1. Key-chart and reading-strip pads are square at every width.
2. The result page title no longer repeats the state tag. It reads "Photo accepted, region measured".
3. Measurements show fixed decimals, for example 17.0 mm instead of 17 mm.
4. The Provenance disclosure has a chevron that turns when it opens.
5. From 600 to 820 px the cases table keeps its rows and folds Basis under the area value. The date header shortens to "Latest exam" so it no longer runs into "State".
6. The placeholder label is HTML at 13 px on a dark chip, so it stays legible at any image size.
7. The case meta line is sans, and only the ID is mono.
8. The refused panel no longer stretches to the height of the image.

Fix 5 caused two regressions: the header split into "Latest exam ination", and case labels truncated at 768 px. The header label is now a single span, and below 820 px the case cell wraps. On recapture the reviewer returned ship.

After the fixes: the 23-route sweep reported no problems, no tablet route overflowed, the contrast check found no failures, and `impeccable detect` returned `[]` on /, /cases, /analyses/a1d093 and /analyses/a1d066. The captures in this folder are from that build. They were taken with reduced motion, because headless Chrome does not advance the pad entrance animation.

## Not tested

- Touch on a physical device. The compare and opacity sliders are native range inputs, so they were not tested with synthesized touch.
- Screen-reader output.
- Text zoom at 200%.
- Firefox and Safari.

## Detector false positives

The small-target script flags `INPUT` elements that are not touch targets:
- the hidden file input inside the dropzone label
- the consent checkbox, whose target is the full-width label
- Base UI's hidden value input in the rows-per-page select
