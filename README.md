# DFU-WoundMonitor

**Computer Vision–Based Longitudinal Diabetic Foot Wound Monitoring System**

Upload a wound photo and the system checks image quality, segments the wound, measures it, stores the result and
compares it with earlier examinations.

> **IMPORTANT MEDICAL NOTICE & DISCLAIMER**
> DFU-WoundMonitor is a research and engineering prototype.
> - It is **NOT** a medical device and has not been clinically validated.
> - It is **NOT** a diagnostic system and does **NOT** provide medical diagnoses.
> - It does **NOT** make treatment decisions or clinical recommendations.
> - It is not intended to replace professional clinical judgment or direct patient assessment by licensed healthcare providers.

## Status

Phases 00–06 are COMPLETED and released as v1.0.0. Phase 07 work (PostgreSQL, object storage, sign-in and
background workers) passes locally, but it has not yet run in CI or a hosted deployment.
Phases 08–10 are specified but not built.

| Measure | Result | Evidence |
|---|---|---|
| FUSeg2021 held-out test, 191 images | Pooled Dice **0.922**, macro Dice **0.841** | [Segmentation report](reports/experiments/spec_02_03_report.md) |
| LowerLimb V3 external check, no tuning | Pooled Dice **0.256** | [Phase 06 report](reports/final/phase_06_validation_report.md) |
| CPU speed | About 5.8 s per image on 2 cores; 97% is segmentation | [Benchmark](reports/final/p06_benchmark.json) |

### Known gaps

- External generalisation is not established. On LowerLimb V3, pooled Dice is 0.26, against 0.92 in-domain. Much of
  the drop appears to come from a different annotation protocol, but that is a hypothesis.
- Real longitudinal patient series are not available. Trends were exercised with constructed examination sequences only.
- Physical units need a scale. Without a supplied `pixels_per_mm`, only pixel values are reported.
- A clean install passes on Windows with Python 3.12. Linux waits for the first CI run (REQ-P06-S03-001 is PARTIAL).
- The Hugging Face Space is packaged but not yet published, so there is no public URL yet.
- DFUC2020, DFUC2021 and DFUC2022 are **blocked** pending the official license application.

## Quick start

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

The tests need no checkpoint or dataset images; two skip when the FUSeg2021 images are absent. To run the service, place the checkpoint at
`models/checkpoints/spec-02-03/resnet34_unet_512_best.pth` (SHA-256 in the [release guide](docs/release/RELEASE.md)),
then:

```bash
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/dashboard>. The API schema is at `/docs`. To confirm the running system works:

```bash
python scripts/deployment/smoke_test.py
```

### Docker / Hugging Face Spaces demo

```bash
docker build -f docker/production/Dockerfile -t dfu-woundmonitor .
```

```bash
docker run --rm -p 7860:7860 -v "$PWD/models:/home/user/app/models" dfu-woundmonitor
```

```bash
python scripts/deployment/build_hf_space.py
```

The checkpoint is fetched at container start from a Hugging Face model repo (`DFU_CHECKPOINT_REPO`) and is used only
if its SHA-256 matches the pinned value. Publishing steps: [docs/deployment/HUGGINGFACE.md](docs/deployment/HUGGINGFACE.md).

## How it works

```text
upload → decode and validate → quality gate → segmentation → measurement → stored record → comparison and trends
                                    │
                                    └─ rejected: stored with reason codes, and the model never runs
```

| Part | Technology |
|---|---|
| Model | ImageNet-pretrained ResNet34 U-Net at 512 px with flip TTA, trained with PyTorch |
| Service | FastAPI, with typed errors and separate health checks for service and model |
| Storage | PostgreSQL or SQLite through SQLAlchemy and Alembic, plus a content-addressed blob store |
| Interface | Static dashboard that uses only the public API |
| Packaging | Docker image and Hugging Face Space bundle |

## Repository structure

```text
src/        Application code: data, segmentation, preprocessing, quality, inference,
            measurement, longitudinal, storage, api, dashboard
scripts/    Entry points: data, training, evaluation, verification, deployment
tests/      Test suites by subsystem
configs/    Versioned data, model, training, quality, measurement and inference configuration
specs/      Requirements: phases 00–10, tracker, traceability, template
docs/       Architecture, API, development, deployment, release, roadmap
data/       Dataset manifests and registry (images are not in git)
models/     Checkpoints (not in git)
reports/    Experiment results and release evidence
docker/     Production image
```

## Documentation

| Read this | To |
|---|---|
| [Documentation index](docs/README.md) | Find anything |
| [System architecture](docs/architecture/system-architecture.md) | Understand the design |
| [API reference](docs/api/API.md) | Call the service |
| [Release guide](docs/release/RELEASE.md) | Install and run it |
| [Development guide](docs/development/DEVELOPMENT.md) | Work on the code |
| [Model card](docs/deployment/MODEL_CARD.md) | Review the model |
| [Production roadmap](docs/roadmap/PRODUCTION_ROADMAP.md) | See what comes next |

## Development method

This repository follows Spec-Driven Development: no implementation proceeds without an approved specification,
measurable requirements and explicit acceptance criteria. `specs/` is the single source of truth, and
[`specs/MASTER_TRACKER.md`](specs/MASTER_TRACKER.md) shows the status of every specification. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

See [LICENSE](LICENSE). Datasets have their own terms, listed in `data/external/dataset_registry.json`. Release
history is in [CHANGELOG.md](CHANGELOG.md).
