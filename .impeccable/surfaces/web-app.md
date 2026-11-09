---
version: 1
slug: "web-app"
primary_target: "web/app"
related_targets: ["web/components"]
---

## Scope and mode

All of `web/`. Operate for the app (cases, upload, analysis, trend, compare, account). Persuade for the landing page. Read for the model page.

Audience, job and constraints live in PRODUCT.md. Backend, auth logic and deployment are out of scope: the UI talks to a clearly labelled mock layer shaped like `/api/v2`.

## Direction contract

THESIS: A refusal is a reading. Every photo is read against a printed key before any measurement exists. Refuses the white-and-teal clinical SaaS dashboard, and its dark imaging-viewer opposite.

OWN-WORLD: The reference colour key printed on a reagent bottle label. Aubergine shell rail, pale reagent-green ground, white label panels, reading colours from the key: pad green, mustard, oxide, magenta. Archivo at normal and condensed widths, tabular figures in a mono for values. Square pads, hairline rules, 2px corners. Dense tables with columns that never move.

STORY: The visitor learns that the system reads a photo first, sees a named reason when it refuses, and sees the 0.92 and 0.26 Dice results together. They then record or inspect an examination and know what each value can support.

FIRST VIEWPORT: App: aubergine left rail with Cases, New analysis, Account; a work area with the cases table, each row carrying its latest strip, value with unit and basis, and state. Landing: the full-width key chart, nine pads across, with one rejected and one accepted reading against it, the headline stating refusal, and Sign in and Model evidence as the two actions.

FORM: Reference colour key, position 6 of 7 on the ordered list, seed:8edd38f9703958ab. Landing structure: the page as the key, position 4 of 5 on the structure list, led by the surface deal. Signature move: the reading strip, nine pads for decode, size, aspect, content, sharpness, underexposure, overexposure, contrast and glare. Each pad carries a drawn mark and a name, so colour is never alone. Pads step to their result in sequence, in hard 90 ms steps with no easing. The strip appears in table rows, on analysis progress, on rejection and on the result.

RAISES: From the Japanese high-density site: a table row carries strip, value, unit, basis and state without whitespace inflation. From the acetate manual: motion is hard two-frame steps, and the mask overlay is the only translucent layer in the product. From the gate board: a row whose state changed stays marked until it is opened. From the split-flap board: columns never move, only their values change.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Unresolved

Auth provider, retention period, and which sample images can ship. The direction ran unattended: the user was not shown a decision page in this session.
