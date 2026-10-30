# Changelog

All dates are commit dates. The project is a research prototype; see the medical notice in `README.md`.

## [Unreleased]

### Added
- Specifications for Phases 07–10 (17 specifications, all `NOT_STARTED`), with tracker, traceability and roadmap entries.
- Documentation index, API reference, design decisions, development, testing and experiment guides, a scripts guide and `CONTRIBUTING.md`.
- `data/external/dataset_registry.json` is now tracked, because the tests need it on a fresh clone.
- Ruff and mypy configuration; `pyproject.toml` reads its dependencies from `requirements.txt`.

- P07-S01: GitHub Actions workflow (lint, types, tests, clean install on Linux and Windows, Docker image) and `check_refuses_bad_model.py`. mypy now reports no errors.
- P07-S02: PostgreSQL support through SQLAlchemy models, a repository layer and Alembic migrations, selected with `DFU_DATABASE_URL`. SQLite stays the local default. `migrate_db.py` applies migrations and `import_sqlite.py` copies a SQLite database with verified counts and checksums.
- P07-S03: `BlobStore` with local and S3 backends, selected by `DFU_STORAGE_BACKEND`. `/api/v2/uploads` issues signed upload URLs, and a stored object is verified for size, hash and format before analysis. `migrate_blobs.py` copies existing blobs and checks every hash. `/health/ready` gains a `storage` field.

- P07-S04: `/api/v2` sign-in through provider JWTs, with `users`, per-user ownership enforced in the repository, 404 for foreign IDs, account export and deletion. `/api/v1` and the dashboard are removed when `DFU_AUTH_ISSUER` is set.
- P07-S05: `src/worker/` runs analyses as arq jobs on Redis. `POST /api/v2/analyses` returns 202, with retries, a sweeper for lost workers and lost messages, 429 when the queue is full, and a `queue` field in `/health/ready`. The Docker build gains a `worker` target. `check_worker_parity.py` compares a real worker with the direct path on the real model.

### Changed
- Scripts moved into `scripts/data`, `training`, `evaluation`, `verification` and `deployment`. `kaggle_jobs/` moved into `scripts/training/kaggle/`.
- README rewritten around current status, quick start and documentation links.
- Lint fixes across `src/`, `scripts/` and `tests/`, with no intended change in behaviour.

### Fixed
- Two FUSeg2021 data tests now skip when the images are absent, so the suite passes on a fresh clone.

### Removed
- Empty placeholder folders and packages: `api/`, `database/`, `frontend/`, `experiments/`, `notebooks/`, `docker/development/`, `src/detection/`, `src/evaluation/` and `src/utils/`.

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
