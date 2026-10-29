# Changelog

All dates are commit dates. The project is a research prototype; see the medical notice in `README.md`.

## [1.0.0] — 2026-10-29

First complete release of Phases 00–06.

### Fixed
- `build_release_manifest.py` takes `--output`, and `git.dirty` ignores the manifest file itself.
  Previously the test suite overwrote the committed `reports/final/release_manifest.json`, and a rebuild
  could never record a clean tree.

### Documentation
- Added this changelog and `docs/roadmap/PRODUCTION_ROADMAP.md` (planned Phase 07 production platform).
- Updated `README.md`, `specs/MASTER_TRACKER.md`, `docs/release/RELEASE.md`, `frontend/README.md` and
  `database/README.md` to the current state.

### Verified on 2026-10-29
- `python -m pytest -q`: 265 passed.
- `python scripts/deployment/smoke_test.py --url http://127.0.0.1:8000`: 8/8 checks passed.
- Dashboard analysis of FUSeg test image 1011: COMPLETED, one region, 1,928 px².

## 2026-10-22 — Phase 06 evidence (`33b2878`)
- End-to-end validation on FUSeg2021 test (pooled Dice 0.922, macro 0.841) and LowerLimb V3 external
  check (pooled Dice 0.256), annotation-form analysis, CPU benchmark, release manifest.

## 2026-10-22 — Docker and Hugging Face packaging (`d177ada`)
- Production Dockerfile, checkpoint fetch with SHA-256 verification, Space bundle builder, deployment docs.

## 2026-10-22 — Phases 03–06 (`6bda353`)
- Inference engine, quality gate, measurement engine, longitudinal records/comparison/trends,
  FastAPI service, SQLite + blob storage, dashboard, validation and release tooling.

## 2026-10-07 — Phase 02 (`158dced`)
- Baseline segmentation, evaluation and validation audit.
