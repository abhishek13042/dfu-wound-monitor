# Marker photo protocol (REQ-P09-S01-003)

REQ-P09-S01-003 needs real photos: the printed marker beside objects of known size, across distances and angles. This page is the shot list. It needs a printer, a phone and a ruler, and costs nothing beyond paper.

No wounds, no people and no patient data are photographed. The photos stay on your machine in `data/raw/marker_photos/`, which git ignores; only the numeric report is committed.

## 1. Print and check the marker

1. Print `docs/measurement/marker_sheet_v1.pdf` at **100% / Actual size**, not "Fit to page".
2. Measure the outlined check square with a ruler. It must be **50 mm** on each side, ±0.5 mm. If not, fix the print settings and print again. A wrongly scaled print makes every result wrong.
3. Keep the sheet flat. Do not fold it.

## 2. Objects of known size

Use at least two:

| Object | Name in the file | Span to mark | True length |
|---|---|---|---|
| A ruler | `ruler-100mm` | The 0 cm tick to the 10 cm tick | 100 mm |
| A bank or ID card (ISO ID-1) | `card-85.6mm` | The long edge, corner to corner | 85.6 mm |

Any object you have measured with a ruler also works; put its length in the name, such as `box-62mm`.

## 3. Shot list

Lay the object flat right beside the marker sheet, on the same surface. Light from a window or ceiling, without hard shadows across the marker. Hold the phone at the distance and angle listed; the angle is the tilt away from looking straight down.

| | 0° (straight down) | 15° | 30° |
|---|---|---|---|
| **20 cm** | ruler, card | ruler, card | ruler, card |
| **30 cm** | ruler, card | ruler, card | ruler, card |
| **40 cm** | ruler, card | ruler, card | ruler, card |

That is 18 photos. Take each twice (36) if you can; the second set shows how much the result varies. Keep the whole marker in frame with a white margin around it. Use the phone's normal 1× camera, no zoom and no portrait mode.

Expect some 30° photos to be refused as `TILTED`. That is the intended behaviour, and the report counts it.

## 4. Name the files

Copy the photos to `data/raw/marker_photos/` and rename each one:

```
d<distance_cm>_a<angle_deg>_<object>-<true_mm>mm_<n>.jpg
```

For example, `d30_a15_ruler-100mm_01.jpg` and `d30_a15_card-85.6mm_02.jpg`. The marking tool reads distance, angle and true length from the name.

## 5. Mark the end points

```bash
python scripts/measurement/mark_object_ends.py data/raw/marker_photos
```

A window opens for each photo, with the marker status from the detector in the title. Use the toolbar's magnifier to zoom in, switch it off, and click the two ends of the span (for the ruler, the centre of the 0 and 10 cm ticks). **Enter** saves, **R** clears the clicks, **S** skips, **Q** stops. The tool writes `data/raw/marker_photos/manifest.json` after every photo, so you can stop and continue later.

## 6. Run the validation

```bash
python scripts/evaluation/run_marker_validation.py --data data/raw/marker_photos/manifest.json
```

This writes `reports/final/p09_s01_marker_validation.json`, with the error by distance and by angle, the share of photos the marker was accepted in, and whether the median absolute error is within the 3% target. Commit that report; do not commit the photos.

Then record the result in `specs/phase-09/01-reference-marker-calibration.md` (status line, the REQ-P09-S01-003 row and the Evidence section), `specs/TRACEABILITY.md` and `specs/MASTER_TRACKER.md`. If the target is missed, report the number as it is; do not change the threshold.

## Manifest format

The tool writes this format; you can also write it by hand. Paths are relative to the manifest, and `p1` and `p2` are image pixels.

```json
{
  "images": [
    {"path": "d30_a15_ruler-100mm_01.jpg", "distance_cm": 30, "angle_deg": 15,
     "object": {"name": "ruler", "p1": [412.0, 300.5], "p2": [1012.0, 304.0], "true_mm": 100.0}}
  ]
}
```
