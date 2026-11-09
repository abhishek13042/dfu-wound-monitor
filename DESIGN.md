---
name: DFU-WoundMonitor
description: A research prototype that reads every photo against a printed key of nine checks before it measures anything.
colors:
  aubergine: "#2a1530"
  aubergine-2: "#41254a"
  rail-ink: "#f3ecf4"
  rail-muted: "#cdbcd1"
  ground: "#e9f0e4"
  panel: "#fdfefb"
  secondary: "#dfe7d9"
  ink: "#1d1620"
  ink-2: "#4b4451"
  rule: "#bcc7b4"
  rule-strong: "#7f8a79"
  pass: "#1f7a4a"
  pass-wash: "#dceee2"
  reject: "#ad3a17"
  reject-wash: "#f8e4dc"
  failure: "#a3146b"
  failure-2: "#7f0f53"
  failure-wash: "#f7e0ee"
  warn: "#d9a514"
  warn-ink: "#664800"
  warn-wash: "#fbf1cf"
  series: "#33578f"
  series-wash: "#dfe6f1"
  pad-none: "#dfe7d9"
  photo-1: "#a79c93"
  photo-2: "#8d8279"
  photo-3: "#6f655e"
  photo-ink: "#f6f2ee"
typography:
  display:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "72px"
    fontWeight: 700
    lineHeight: "72px"
    fontVariation: "'wdth' 75"
  headline:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "40px"
    fontWeight: 700
    lineHeight: "42px"
    fontVariation: "'wdth' 78"
  title:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "28px"
    fontWeight: 700
    lineHeight: "32px"
    fontVariation: "'wdth' 78"
  title-sm:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "20px"
    fontWeight: 700
    lineHeight: "26px"
    fontVariation: "'wdth' 78"
  body:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: "24px"
  body-sm:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: "20px"
  caption:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: "18px"
  label:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: "16px"
  value:
    fontFamily: "Spline Sans Mono, ui-monospace, monospace"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: "18px"
    fontFeature: "'tnum' 1"
rounded:
  sm: "2px"
spacing:
  pad-gap: "2px"
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  section: "56px"
  target: "44px"
components:
  button-primary:
    backgroundColor: "{colors.aubergine}"
    textColor: "{colors.rail-ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    padding: "0 16px"
    height: "40px"
  button-primary-hover:
    backgroundColor: "{colors.aubergine-2}"
  button-outline:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "0 16px"
    height: "40px"
  button-outline-hover:
    backgroundColor: "{colors.secondary}"
  button-destructive:
    backgroundColor: "{colors.failure}"
    textColor: "#ffffff"
    rounded: "{rounded.sm}"
    padding: "0 16px"
    height: "40px"
  button-destructive-hover:
    backgroundColor: "{colors.failure-2}"
  field:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "9px 12px"
    height: "44px"
  panel:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.sm}"
  rail:
    backgroundColor: "{colors.aubergine}"
    textColor: "{colors.rail-ink}"
    width: "220px"
  rail-item-active:
    backgroundColor: "{colors.rail-ink}"
    textColor: "{colors.aubergine}"
    rounded: "{rounded.sm}"
    height: "44px"
  pad-pass:
    backgroundColor: "{colors.pass}"
    textColor: "{colors.panel}"
    rounded: "{rounded.sm}"
    size: "16px"
  pad-fail:
    backgroundColor: "{colors.reject}"
    textColor: "{colors.panel}"
    rounded: "{rounded.sm}"
    size: "16px"
  pad-none:
    backgroundColor: "{colors.pad-none}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.sm}"
    size: "16px"
  refusal-panel:
    backgroundColor: "{colors.reject-wash}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "20px"
  failure-panel:
    backgroundColor: "{colors.failure-wash}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "16px"
  warning:
    backgroundColor: "{colors.warn-wash}"
    textColor: "{colors.ink}"
    padding: "8px 12px"
---

# Design System: DFU-WoundMonitor

## Overview

**Creative North Star: "The Reagent Key"**

The system is built like the colour key printed on a reagent bottle label. A dark aubergine shell holds pale reagent-green ground, white label panels sit on that ground, and every result is read against a row of square pads in fixed reading colours. Each colour means one thing. Green is pass, rust is a quality refusal, magenta is a system failure, amber is a caution, and blue is the one hue that carries no verdict at all.

Density is high and calm. A table row carries the strip, the value with its unit and basis, the date and the state without extra whitespace, and the columns stay where they are while only the values change. Hairline rules separate things, 2px corners keep everything square, and there is almost no shadow. Archivo, narrowed to 78% width, sets every heading. A tabular mono is used only for values. Motion is a hard step with no easing.

The build is light-only on purpose. It is neither a white-and-teal clinical dashboard nor a dark imaging viewer.

**Key Characteristics:**
- Aubergine shell (rail or header), reagent-green ground, white panels with hairline borders.
- Five verdict-bearing hues and one neutral series hue, never swapped.
- Square pads with a drawn mark (tick, cross, dash), so colour never stands alone.
- 2px radius on every surface and control.
- Condensed Archivo headings, Spline Sans Mono only for values, IDs and dates.
- Pads step to their result in hard 90 ms frames. Nothing else moves.

## Colors

The palette is a printed reading key. The neutrals come from the label and the bottle, and the saturated colours are the readings.

### Primary
- **Aubergine Shell** (aubergine): the rail, the public header, the landing hero band, the primary button, text selection, the caret, range-input accents and the modal scrim. It is the bottle, not a reading.
- **Lifted Aubergine** (aubergine-2): hover state on the rail and on primary buttons, the rule inside the rail, and the focus ring colour on light ground.
- **Label Ink on Aubergine** (rail-ink): text on the shell, and the background of the active rail item, which flips to aubergine text.
- **Faded Label Ink** (rail-muted): secondary text on the shell, and the outline of unread pads placed on aubergine.

### Secondary (the reading colours)
- **Pad Green** (pass): an accepted check, a measured result, a ready service. Pass pads, the Measured state tag, and the Measured outcome on the key chart.
- **Oxide Rust** (reject): a quality refusal, meaning the photo failed a named check and no value exists. Fail pads, failed check names, the Refused state tag, the refusal panel border, invalid field borders, inline upload problems, and the dashed Excluded line on the trend chart.
- **Reagent Magenta** (failure): a system failure, meaning the service broke and the photo was not judged. The Failed state tag, the failure panel border, the error page title, and destructive actions such as delete. **Deep Magenta** (failure-2) is the destructive button's hover.
- **Mustard** (warn): caution borders only, on the medical notice bar and on warning rows. It is never used for text.
- **Mustard Ink** (warn-ink): the text form of caution. Warning icons, the constructed-data notice, and the Changed marker on a case row whose state changed since it was last opened.
- **Washes** (pass-wash, reject-wash, failure-wash, warn-wash): a pale fill behind a panel or row that carries the matching verdict. A wash always comes with its full-strength border or text.

### Tertiary
- **Series Blue** (series): the one hue that carries no verdict. It fills the segmentation mask overlay, colours the Running state, and strokes the calibrated trend line. It must never read as pass, reject or failure. **Series Wash** (series-wash) is defined as its pale companion.

### Neutral
- **Reagent Ground** (ground): the page background everywhere outside the shell.
- **Label White** (panel): every panel, card, table, field and popover surface.
- **Pale Reagent** (secondary, also pad-none): unread pads, disabled fields, and the hover fill of outline and ghost buttons, table rows, and the upload area while a file is dragged over it. Hover never uses a reading colour.
- **Ink** (ink): body text and headings.
- **Second Ink** (ink-2): metadata, column headers, units, captions and placeholders.
- **Hairline** (rule): panel borders, table rules and chart gridlines.
- **Strong Rule** (rule-strong): field borders, unread-pad outlines, axis lines, link underlines at rest, and the scrollbar thumb.
- **Placeholder Stone** (photo-1, photo-2, photo-3, photo-ink): only for the constructed placeholder image and its label chip. These are never used in the interface.

### Named Rules
**The One Meaning Rule.** Pass is green, a quality refusal is rust, and a system failure is magenta. The three are never interchangeable, and none of them ever decorates. If a colour does not state a verdict, it is a neutral or Series Blue.

**The No-Verdict Hue Rule.** Series Blue is the only colour for states and data that have no verdict yet or need none: the mask, Running, and the calibrated series. Do not use a verdict colour for an in-progress state, and do not use Series Blue for a result.

**The Ink-for-Text Rule.** Mustard is a border and fill colour. Caution text and icons always use Mustard Ink.

## Typography

**Display Font:** Archivo (variable width axis), with system-ui fallback
**Body Font:** Archivo, with system-ui fallback
**Label/Mono Font:** Spline Sans Mono, with ui-monospace fallback

**Character:** One grotesque at two widths: condensed and bold for headings, normal width for reading. A tabular mono sits beside it for the numbers you read off a label.

### Hierarchy
- **Display** (700, 72px/72px, 75% width): the landing headline from 640px up. It drops to Headline on phones.
- **Headline** (700, 40px/42px, 78% width): page titles from 640px up, and the Pooled Dice figures in mono.
- **Title** (700, 28px/32px, 78% width): page titles on phones and section headings on the landing page.
- **Title Small** (700, 20px/26px, 78% width): panel headings such as Measurements, Why it was refused, and dialog titles.
- **Body** (400, 16px/24px): running text and field input. Paragraphs are capped at 60 to 75ch, and wrapping is set to pretty.
- **Body Small** (400 to 600, 14px/20px): table cells, buttons (500), navigation (500), check names (600) and panel copy.
- **Caption** (400, 13px/18px): column headers, units, metadata lines, provenance rows and the placeholder label.
- **Label** (400, 600 for emphasis, 12px/16px): pad names under a standard strip, stacked-row field labels and the Changed marker.
- **Value** (Spline Sans Mono, tabular figures, inheriting the size of its context): every number, unit, ID, hash, model version and date.

### Named Rules
**The Mono Is Data Rule.** Spline Sans Mono appears only on values, IDs and dates. It is never used for a heading, a label, a button or decoration. A metadata line is sans, with only the ID inside it in mono. When a value cell has no value ("None"), the word goes back to sans.

**The Condensed Heading Rule.** Headings 1 to 3 are Archivo Bold at 78% width with balanced wrapping. Width carries the hierarchy, so headings never go uppercase or get letter-spacing.

**The Fixed Precision Rule.** Values in a column show the same number of decimals (17.0 mm, never 17 mm). Physical values use one decimal, pixel values none. Negative values use a true minus sign. Dates read "31 Oct 2026".

## Layout

- **App shell.** From 900px up, a sticky aubergine rail 220px wide sits beside a work area capped at 1180px. Below 900px the rail becomes a 56px top bar with a menu toggle. A sticky mustard-bordered medical notice runs across the top of every page.
- **Public shell.** An aubergine header 56px tall, with content capped at 1320px. The landing hero continues the aubergine into a band that holds the full-width key chart.
- **Gutters.** 16px on phones and 24px from 640px up. Pages begin 24px below the notice, and landing sections are separated by 56px.
- **Rhythm.** A 4px base. Hit targets and dense table rows are 44px, buttons are 40px (44px when large), and panel padding is 16 to 20px. Pads in a compact strip sit 2px apart.
- **Dense tables, fixed columns.** Tables have fixed layout and assigned column widths, so columns never shift when values change.
- **Responsive tables.** Below 640px viewport width, any stacked table turns each row into a labelled block: the header is hidden from sight, each cell shows its label in 12px Second Ink above the value, and wide cells (label, reading strip) span the full row.
- **The cases table follows its own width.** It is a size container. Below 600px of container width it stacks into labelled blocks in an auto-fitting grid of 140px minimum columns. From 600 to 820px it keeps its rows, hides the Basis column, folds the basis under the area value, and shortens the date header to "Latest exam". The rail narrows the table, so viewport breakpoints are not enough here.
- **Key chart.** From 768px up it is a ten-column table (one label column, nine pads). Below 768px it turns into a vertical list of checks with two pad columns, Photo A and Photo B.

## Elevation & Depth

The system is flat. Depth comes from tone: panels in Label White on Reagent Ground, framed by a 1px Hairline. The aubergine shell is the darkest layer. Only floating layers have a shadow.

### Shadow Vocabulary
- **Menu** (`box-shadow: 0 6px 20px rgb(42 21 48 / 0.2)`): the chart tooltip and the confirmation dialog only, tinted with aubergine.

### Named Rules
**The Flat Label Rule.** Panels, tables, pads and buttons have no shadow. If a surface does not float above the page, it has no shadow.

**The One Translucency Rule.** The segmentation mask, in Series Blue at an opacity the user sets (55% by default), is the only translucent layer drawn over content. The modal scrim (aubergine at 70%) is the only other translucent layer, and it covers the page, not content.

## Shapes

Every corner is 2px. Each radius step in the theme resolves to 2px, so a "large" or "pill" request still renders square. Borders are 1px hairlines. Unread pads use an inset 1px outline instead of a border so their size stays exact. Pads are always square: 16px in table rows, 28px (36px from 640px) in a standard strip, and 48px (56px from 1024px) in the key chart. The one exception is the phone key chart, where each pad fills the width of its cell. The wordmark is three 10px square pads (green, mustard, rust) beside the name.

## Components

### Buttons
Solid and square, with no lift.
- **Shape:** 2px corners, 40px tall with 16px side padding, or 44px tall with 20px padding at large size. Label in 14px Archivo at weight 500, with 16px icons.
- **Primary:** Aubergine Shell fill with Label Ink text. Hover lifts to Lifted Aubergine. On the aubergine hero the colours invert: Label Ink fill with aubergine text.
- **Outline:** a Hairline border on Reagent Ground, with a Pale Reagent fill on hover. Pagination uses 40px square icon buttons.
- **Destructive:** Reagent Magenta fill with white text, and Deep Magenta on hover. A destructive trigger is an outline button with a magenta border and text and a magenta-wash hover.
- **Focus:** the global 2px outline in Lifted Aubergine, offset 2px, which becomes Label Ink on the shell. Disabled buttons drop to 50% opacity.

### Inputs / Fields
- **Style:** Label White fill, a 1px Strong Rule border, 2px corners, 44px minimum height, 9px by 12px padding, and 16px text.
- **Hover / Focus:** the border darkens to Ink on hover. Focus uses the global 2px outline. The filter field in the cases table puts the outline around its whole bar.
- **Error / Disabled:** an invalid field gets an Oxide Rust border with an inline rust message. A disabled field has a Pale Reagent fill and Second Ink text.

### Navigation (Rail)
- Rail items are 44px tall with 2px corners, 14px weight-500 labels and 16px line icons. The active item inverts to a Label Ink fill with aubergine text, and hover fills with Lifted Aubergine.
- A Service readiness list sits at the foot of the rail: 13px rows, each with a 14px pass or fail pad.

### Panels
- **Corner Style:** 2px.
- **Background:** Label White on Reagent Ground.
- **Border:** a 1px Hairline. A panel that carries a verdict switches to that verdict's border and wash (rust for a refusal, magenta for a failure).
- **Internal Padding:** 16px, or 20px for primary content. Panel tables put their own 1px rules between rows.

### Reading Strip (signature)
Nine square pads in a fixed order: decode, size, aspect, content, sharpness, underexposure, overexposure, contrast, glare.
- **States:** pass (green fill, white tick), fail (rust fill, white cross), and not read (Pale Reagent fill, Strong Rule inset outline, Second Ink dash). The mark is drawn with a 2.4 stroke and square caps.
- **Compact:** 16px pads, 2px apart, followed by the failed check names in 13px rust. Used in table rows.
- **Standard:** 28 to 36px pads, each with a 12px name beneath it. A failed name turns rust and semibold. On phones it is a three-column grid, and from 640px it is nine across.
- **Motion:** while an analysis is pending, and on a refusal, each pad holds as unread and then snaps to its result in sequence, 90ms per step with a steps(1) timing and no easing. With reduced motion, the result shows immediately.
- **Accessibility:** the strip has one spoken summary ("7 of 9 checks passed; failed: Sharpness, Glare").

### State Tag
14px weight-500 text with a 16px lead. Measured and Refused carry a pass or fail pad. Queued (Second Ink, clock), Running (Series Blue, spinner) and Failed (magenta, alert octagon) carry a line icon. It is never a filled pill.

### Refusal and Error Panels
- **Refusal:** rust border on rust wash, a Title Small heading, each failed check named with its retake instruction, and the primary action "Retake and upload".
- **Failure:** magenta border on magenta wash, with a mono request ID.
- **User-side errors** (invalid input, not found): a neutral Strong Rule border.

### Warning Row and Medical Notice
A Mustard border on Mustard Wash, 8px by 12px padding, 14px text, and a Mustard Ink triangle icon. The notice bar is 13px, sticky, and has a Mustard rule at the bottom.

### Constructed Placeholder Photo
A drawn stone-toned stand-in (photo-1 to photo-3) with a scale tick ruler, until real sample images are supplied. Its accessible name says it is a constructed placeholder, not a photograph. A visible chip at the top left reads "Constructed placeholder, no photograph". The chip is HTML at 13px, Placeholder Ink on the darkest stone, so it stays legible at any image size. Anything that stands in for a real photograph must carry this marking.

### Measurements and Provenance
Measurements are panel tables with 44px rows: a 14px sans label, a right-aligned 20px mono value, and a 13px mono unit in Second Ink. Provenance is a disclosure panel. Its chevron turns 90° on open with no transition, and it holds 13px label/value rows on a 110px label column.

## Do's and Don'ts

### Do:
- **Do** state every result with a pad mark or a word as well as its colour. Colour never stands alone.
- **Do** use Oxide Rust for a quality refusal, Reagent Magenta for a system failure and Pad Green for a pass, each with its own wash. Use Series Blue for the mask, Running and the calibrated series.
- **Do** keep every corner at 2px and every pad square.
- **Do** set values, units, IDs, hashes, versions and dates in Spline Sans Mono with tabular figures, at fixed precision per column.
- **Do** keep table columns at fixed widths. On narrow widths, stack rows into labelled blocks instead of letting the columns move.
- **Do** use Mustard Ink for caution text and keep Mustard for borders and fills.
- **Do** make hit targets at least 44px tall and use the global 2px Lifted Aubergine focus outline.
- **Do** mark any stand-in image as constructed, in both its accessible name and its visible label.

### Don't:
- **Don't** use Pad Green, Oxide Rust or Reagent Magenta as interchangeable "error" or "accent" colours, or as decoration.
- **Don't** show a Running or pending state in a verdict colour.
- **Don't** set Mustard text on a light ground.
- **Don't** use mono for headings, labels, buttons or ornament.
- **Don't** add shadows to panels, pads or buttons. The menu shadow is for floating layers only.
- **Don't** ease or tween result motion. Pads snap in hard steps.
- **Don't** round pads or turn state tags into pills.
- **Don't** add a translucent layer over content other than the segmentation mask.
