# P01-S06 — EDA and Annotation Visualization

## Purpose
Understand the real data before model development: image characteristics, annotation distributions, quality problems, and split differences.

## Requirements
- **REQ-P01-S06-001:** Report image count, annotated count, missing annotations, dimensions, formats, channels, and validation status.
- **REQ-P01-S06-002:** Analyze width, height, aspect ratio, and unusual dimensions.
- **REQ-P01-S06-003:** For boxes, analyze boxes/image, class distribution, width/height, area, normalized area where useful, and extremes.
- **REQ-P01-S06-004:** For masks, analyze presence, area, mask/image ratio, empty masks, extremes, and label distribution where applicable. Do not call these clinical measurements.
- **REQ-P01-S06-005:** Where metadata exists, analyze patients, examinations/visits, samples per patient/exam, and repeated observations. State when unavailable.
- **REQ-P01-S06-006:** After P01-S05, compare split distributions for counts, classes, dimensions, annotation sizes, and patient/exam counts.
- **REQ-P01-S06-007:** Create reproducible image+box, image+mask, and relevant-label overlays.
- **REQ-P01-S06-008:** Visualize representative P01-S03 problem cases.
- **REQ-P01-S06-009:** EDA must regenerate from recorded inputs/configuration.
- **REQ-P01-S06-010:** Do not cherry-pick examples; use deterministic/documented sampling.
- **REQ-P01-S06-011:** Combined statistics are allowed only when dataset labels/annotation semantics are compatible and the combination is documented.

## Recommended report
Dataset inventory; dimensions/aspect ratios; label distributions; detection stats; segmentation stats; patient/exam stats; split stats; quality issues; annotation grids; observations and unresolved questions.

## Acceptance
Every verified dataset has reproducible EDA; major distributions are quantified; annotations and problem cases are visually inspected; split distributions are checked; no unsupported clinical conclusions are drawn.

## Out of scope
Training, hyperparameter tuning, segmentation performance, healing/progression claims, clinical conclusions.
