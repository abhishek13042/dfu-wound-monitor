# Development guide

## Setup

Requires Python 3.11+. Verified with 3.14 on Windows 11, CPU only.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/macOS: source .venv/bin/activate)
python -m pip install -e ".[dev]"
```

`requirements.txt` is the only list of runtime dependencies, and `pyproject.toml` reads it. The tests need neither
the checkpoint nor the datasets. Running the real service needs the checkpoint; see the
[release guide](../release/RELEASE.md).

## Commands

| Command | Does |
|---|---|
| `make test` | Runs the test suite |
| `make lint` | Runs ruff and mypy; both are clean and CI enforces them |
| `make format` | Applies ruff auto-fixes |
| `make run` | Starts the API and dashboard on `127.0.0.1:8000` |
| `make smoke` | Runs the end-to-end smoke test (needs the checkpoint) |
| `make docker` | Builds the production image |
| `make clean` | Removes caches |

Without `make` (the default on Windows), run the matching command from the `Makefile`.

## Repository layout

```text
src/            Application code
  data/           Ingestion, validation, splitting, FUSeg loader, EDA
  segmentation/   Dataset, models, augmentation, trainers, metrics
  preprocessing/  Image decoding and input validation
  quality/        Image quality gate
  inference/      Model engine and end-to-end pipeline
  measurement/    Area, perimeter, Feret diameters, calibration
  longitudinal/   Records, comparison policy, technical trends
  storage/        Models, repository, Alembic migrations, blob store
  api/            FastAPI service, schemas, sign-in, rendering
  worker/         Job states, queue, retry and sweep logic, arq settings
  dashboard/      Static dashboard served at /dashboard
scripts/        Command-line entry points, grouped by purpose
tests/          Test suites, grouped by subsystem
configs/        Versioned JSON configuration
specs/          Specifications, tracker and traceability
docs/           Guides and reference documents
data/           Datasets (git holds manifests and the registry only)
models/         Checkpoints (not in git)
reports/        Results and evidence
docker/         Production image
```

Dependencies point one way: `api`, `worker` → `inference` → `quality`, `measurement`, `segmentation` → `preprocessing`.
Model code never imports the API, and the dashboard reaches the system only through HTTP.

## Running a worker

The default local run needs no Redis, and `/api/v1` runs the model inside the request. To try the queue, start Redis
and run the API and a worker with the same data folder:

```bash
export DFU_REDIS_URL=redis://127.0.0.1:6379 DFU_DATA_DIR=runtime
python -m arq src.worker.settings.WorkerSettings
```

The worker verifies the checkpoint before it takes a job. Use Linux, macOS or Docker for a real worker: on Windows it
runs, but arq cannot shut it down cleanly, because Windows has no `SIGUSR1`.

## Code style

- Ruff settings in `pyproject.toml` are the standard. Line length is 120.
- Use built-in generics and `X | None` for types.
- Pass settings through `configs/`, not constants scattered in code.
- Use typed errors with a stable `code`, as in `src/inference/errors.py`.
- `src/segmentation/config.py` is frozen and excluded from lint. Do not change it without a spec.
- Scripts add the repository root to `sys.path`, so they run directly from the root.

## Adding a feature

1. Write or update the spec from `specs/SPEC_TEMPLATE.md`.
2. Implement it, with tests beside the matching subsystem.
3. Record the evidence and update `specs/TRACEABILITY.md` and `specs/MASTER_TRACKER.md`.
4. Add the change to `CHANGELOG.md`.

## Making a release

Follow the checklist in the [release guide](../release/RELEASE.md). Rebuild the release manifest after everything
else is committed, because it records the commit and the hash of each evidence file.
