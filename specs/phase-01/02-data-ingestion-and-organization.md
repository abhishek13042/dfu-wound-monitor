# P01-S02 — Data Ingestion and Organization

## Purpose
Bring only verified datasets into the project in a reproducible, provenance-preserving way without modifying original data.

## Data layers
Use a clear separation such as `data/raw`, `data/interim`, `data/processed`, and `data/manifests`, following existing repository conventions. Raw data is immutable.

## Requirements
- **REQ-P01-S02-001:** Ingest only datasets passing P01-S01.
- **REQ-P01-S02-002:** Never edit, resize, relabel, or overwrite raw source files in place.
- **REQ-P01-S02-003:** Preserve dataset name/version, source identifier/path, project path, and annotation path.
- **REQ-P01-S02-004:** Record deterministic SHA-256 checksums where practical.
- **REQ-P01-S02-005:** File discovery must be deterministic.
- **REQ-P01-S02-006:** Document supported image/annotation formats and report unsupported files rather than silently ignoring them.
- **REQ-P01-S02-007:** Produce an ingestion report covering discovered, accepted, unsupported, missing, duplicate, and errored files.
- **REQ-P01-S02-008:** Re-running ingestion must be safe and deterministic.
- **REQ-P01-S02-009:** No silent transformations or label changes.
- **REQ-P01-S02-010:** Dataset-specific paths/settings should be configuration-driven, not scattered hard-coded values.

## Acceptance
Verified datasets are reproducibly ingested; raw data remains unchanged; samples are traceable; integrity/provenance are recorded; failures are visible; no model-specific preprocessing is introduced.

## Out of scope
Augmentation, model resizing/normalization, split assignment, training, inference, API/database/frontend.
