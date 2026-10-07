# P01-S04 — Dataset Schema and Label Harmonization

## Purpose
Define a consistent internal representation while preserving each dataset's original semantics. **Standardize representation, not meaning.**

## Canonical metadata
Support fields such as `dataset_name`, `dataset_version`, `source_sample_id`, `image_path`, `annotation_path`, `checksum`, `width`, `height`, `channels`, `annotation_type`, `patient_id`, `exam_id`, `original_label`, `canonical_label`, `metadata_status`, and `validation_status`. Missing source fields remain null/unknown.

## Requirements
- **REQ-P01-S04-001:** Preserve source dataset identity and sample identifier.
- **REQ-P01-S04-002:** Preserve original labels alongside any canonical labels.
- **REQ-P01-S04-003:** Every conversion has an explicit source→canonical mapping with status and notes.
- **REQ-P01-S04-004:** Only semantically compatible labels may map to the same canonical concept; uncertain mappings remain unresolved.
- **REQ-P01-S04-005:** Keep task representations separate for detection, wound segmentation, tissue segmentation, and classification/technical labels.
- **REQ-P01-S04-006:** Define and test one internal box convention, e.g. `x_min,y_min,x_max,y_max`.
- **REQ-P01-S04-007:** Define internal mask dimensions, encoding, and background convention while retaining source encoding documentation.
- **REQ-P01-S04-008:** Never fabricate patient IDs, visit IDs, tissue classes, or clinical meanings from filenames unless source documentation supports it.
- **REQ-P01-S04-009:** Do not blindly merge datasets merely because file formats match.
- **REQ-P01-S04-010:** Validate canonical records for required fields, types, paths, references, and identifier consistency.

## Acceptance
All ingested datasets can be represented; source identity/labels remain traceable; mappings are explicit; incompatibilities and missing metadata are visible; geometry conventions are defined and tested.

## Out of scope
Inventing clinical semantics, blind merging, training, final model tensors.
