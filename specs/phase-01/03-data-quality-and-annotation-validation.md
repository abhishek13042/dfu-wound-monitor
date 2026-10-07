# P01-S03 — Data Quality and Annotation Validation

## Purpose
Identify image and annotation problems before model development. Do not silently delete inconvenient samples; make every problem traceable.

## Requirements
- **REQ-P01-S03-001:** Attempt deterministic decoding of every ingested image and record failures.
- **REQ-P01-S03-002:** Record width, height, channels, format, and file size where available; report unusual values.
- **REQ-P01-S03-003:** Parse every associated annotation and report malformed files.
- **REQ-P01-S03-004:** Validate boxes for positive geometry, coordinate validity, bounds, and valid classes; do not silently clip invalid boxes.
- **REQ-P01-S03-005:** Validate masks for readability, dimensions, valid encoding/labels, expected non-empty content where applicable, and geometry.
- **REQ-P01-S03-006:** Detect images without expected annotations and annotations without corresponding images.
- **REQ-P01-S03-007:** Detect exact duplicates using checksums. Any stronger duplicate check must be explicitly documented.
- **REQ-P01-S03-008:** Categorize issues: unreadable, malformed annotation, invalid geometry, missing annotation, empty annotation, unsupported format, duplicate, unusual dimensions, or other reviewed issue.
- **REQ-P01-S03-009:** Preserve raw files; use issue lists/quarantine references instead of destructive edits.
- **REQ-P01-S03-010:** Produce machine-readable sample-level validation output.
- **REQ-P01-S03-011:** Produce a human-readable summary and representative problematic samples.

## Visual review
Create deterministic examples of valid and problematic boxes/masks, boundary violations, empty masks, and unusual dimensions.

## Acceptance
All ingested samples are checked; failures are reported; geometry is validated; raw files are untouched; results are reproducible; representative failures are inspectable.

## Out of scope
Manual annotation correction, relabeling, training, augmentation, clinical interpretation.
