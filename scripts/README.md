# Scripts

Run every script from the repository root, for example `python scripts/data/run_phase_01_pipeline.py`. Most accept
`--help`. Scripts that write evidence overwrite the committed file, so review the diff before keeping it.

## `data/` — manifests and dataset checks

| Script | Purpose |
|---|---|
| `run_phase_01_pipeline.py` | Runs the Phase 01 ingestion, validation, splitting and EDA pipeline |
| `build_fuseg2021_manifest.py` | Builds the official FUSeg2021 manifest and quality report |
| `build_fuseg2021_heldout_manifest.py` | Derives the held-out split used by SPEC-02-03 |
| `build_lowerlimb_external_manifest.py` | Builds the LowerLimb V3 external manifest |
| `check_near_duplicates.py` | Finds near-duplicate images across collections |

## `training/` — model training

| Script | Purpose |
|---|---|
| `run_phase_02_training.py` | Trains the Phase 02 baseline |
| `run_spec_02_03.py` | Trains and evaluates the ResNet34 U-Net (GPU expected) |
| `kaggle/launch_kaggle_spec_02_03.py` | Stages data and code, then pushes and downloads the Kaggle run |
| `kaggle/spec_02_03_kernel.py` | Entry point that runs inside the Kaggle kernel |
| `kaggle/run_kaggle_spec_02_01.py` | Kaggle wrapper for the baseline run |

## `evaluation/` — validation and benchmarks

| Script | Purpose |
|---|---|
| `run_phase_02_evaluation.py` | Evaluates the baseline |
| `calibrate_quality_gate.py` | Measures quality signals on real images and rewrites `reports/quality/quality_gate_calibration.json` |
| `run_phase_06_validation.py` | Runs end-to-end validation on a labelled set |
| `run_phase_06_benchmark.py` | Measures CPU latency, memory and repeatability |
| `inspect_lowerlimb_annotations.py` | Analyses LowerLimb annotation styles |

## `verification/` — independent checks

| Script | Purpose |
|---|---|
| `verify_phase_00.py` | Checks that specs, tracker and traceability are complete |
| `verify_phase_02_metrics.py` | Recomputes metrics from saved predictions |

## `deployment/` — packaging and release

| Script | Purpose |
|---|---|
| `smoke_test.py` | End-to-end check, in process or against a running server |
| `build_release_manifest.py` | Writes `reports/final/release_manifest.json` |
| `build_hf_space.py` | Assembles the Hugging Face Space bundle in `dist/hf_space/` |
| `fetch_checkpoint.py` | Downloads the checkpoint and verifies its SHA-256 |
| `migrate_db.py` | Applies database migrations |
| `import_sqlite.py` | Copies a SQLite database into PostgreSQL, with verified counts and checksums |
| `migrate_blobs.py` | Copies stored blobs to another backend and checks every hash |
| `check_worker_parity.py` | Compares a real worker with the direct path on the real model, and kills a worker mid-job |
