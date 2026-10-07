# Data Directory

This directory contains the dataset storage structure for DFU-WoundMonitor.

## Directory Structure

- `raw/`: Immutable, original raw images and annotations directly from source datasets.
- `interim/`: Intermediate transformations, staged conversions, or unstandardized splits.
- `processed/`: Canonical, preprocessed, validated, and normalized datasets formatted for training and evaluation pipelines.
- `external/`: External reference standards, third-party metadata, calibration charts, or baseline masks.

## Important Policies

1. **No Large Data in Version Control**:
   All image data, binary masks, and large annotations are excluded from Git via `.gitignore`.
2. **Immutable Raw Data**:
   Files placed in `raw/` are treated as read-only. Any transformations or cleanings must write to `interim/` or `processed/`.
3. **Traceability**:
   Dataset provenance, versioning, licenses, splits, and acquisition scripts are formally specified in Phase 01 (Dataset & Data Engineering).
4. **Acquisition Status**:
   No datasets are acquired, downloaded, or processed during Phase 00 (Project Setup).
