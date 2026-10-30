# Testing guide

```bash
python -m pytest -q
python -m pytest tests/api -q                # one suite
python -m pytest -q -k quality               # by name
```

The suite runs on CPU and takes about 4 minutes. It needs no GPU, checkpoint, dataset or network. S3 tests use
moto. Tests that need a real Redis start `redis-server` themselves, and they skip when it is not installed.

## Suites

| Folder | Covers |
|---|---|
| `tests/unit/` | Phase 00–02: spec integrity, data pipeline, FUSeg contract, baseline and SPEC-02-03 engineering |
| `tests/integration/` | Inference engine and end-to-end pipeline |
| `tests/quality/` | Image quality gate |
| `tests/measurement/` | Geometry and calibration against known masks |
| `tests/longitudinal/` | Records, comparison policy, trends |
| `tests/api/` | HTTP contract, error envelope, uploads, sign-in, ownership |
| `tests/storage/` | Repository, migrations, import, blob contract |
| `tests/worker/` | Job states, redelivery, retries, sweeper, real Redis and arq workers |
| `tests/release/` | Docker and Space packaging, release manifest, claim checks |

## Fixtures

`tests/conftest.py` builds a tiny random ResNet18 U-Net with `pretrained=False`, plus matching configs. It runs the
real code path without the 293 MB checkpoint or a weight download. Its outputs are meaningless, so tests must assert
contracts and never segmentation quality.

## Real services

These variables point the same tests at a real service. CI sets them.

| Variable | Runs on |
|---|---|
| `DFU_TEST_DATABASE_URL` | PostgreSQL, for `tests/storage`, `tests/api` and `tests/worker` |
| `DFU_TEST_S3_ENDPOINT` | MinIO or another S3-compatible store, for the blob contract tests |
| `DFU_TEST_REDIS_URL` | An existing Redis instead of a private one |

## Rules

- Keep `pretrained=False` in tests.
- Write outputs to `tmp_path`. A test must not change a committed file.
- Test failure paths as well as success.

## What the tests do not prove

Tests show that the software meets its contracts. They do not show that the model is accurate. Accuracy evidence
comes from the reports below, and those runs need the checkpoint and datasets.

| Claim | Evidence |
|---|---|
| Held-out segmentation result | `reports/experiments/spec_02_03_report.md` |
| End-to-end and external results | `reports/final/phase_06_validation_report.md` |
| Speed and repeatability | `reports/final/p06_benchmark.json` |
| Real checkpoint works through the service | `python scripts/deployment/smoke_test.py` |
| Worker gives the same answer as the direct path, and survives a killed process | `python scripts/deployment/check_worker_parity.py` (needs the checkpoint and images) |
