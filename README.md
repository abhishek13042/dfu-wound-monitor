# DFU-WoundMonitor

**Computer Vision–Based Longitudinal Diabetic Foot Wound Monitoring System**

Upload a photo of a diabetic foot ulcer. The system checks image quality, outlines the wound with a ResNet34 U-Net,
measures it, shows how confident the model is, lets a clinician correct the outline, and follows the wound across
later photos.

> **IMPORTANT MEDICAL NOTICE & DISCLAIMER**
> DFU-WoundMonitor is a research and engineering prototype.
> - It is **NOT** a medical device and has not been clinically validated.
> - It is **NOT** a diagnostic system and does **NOT** provide medical diagnoses.
> - It does **NOT** make treatment decisions or clinical recommendations.
> - It is not intended to replace professional clinical judgment or direct patient assessment by licensed healthcare providers.

## Try it

| Link | What it is |
|---|---|
| [Browser demo on Hugging Face](https://huggingface.co/spaces/abhishek1402/dfu-woundmonitor) | The quality checks and the model run in your own browser (ONNX Runtime Web). Nothing is uploaded to a server. |
| [Model on Hugging Face](https://huggingface.co/abhishek1402/dfu-resnet34-unet) | The trained model weights and model details |
| Dashboard in demonstration mode | The full web app with constructed data and no sign-in. Deploy it free with [docs/deployment/VERCEL.md](docs/deployment/VERCEL.md), or run it locally (below). |

The full system (API, job queue, worker and sign-in) needs always-on hosting, so it runs locally rather than online.

## Status

| Phase | State |
|---|---|
| 00–06: data, model, quality gate, measurement, trends, API, release | COMPLETED, released as v1.0.0 |
| 07: PostgreSQL, sign-in and per-user data, Redis job queue, ONNX serving, CI | Built; CI runs on GitHub Actions. A hosted object store and the Docker Space are still open. |
| 08: Next.js web app (cases, upload, results, timeline, comparison) | Built and tested end to end against a local API, worker and identity provider; not deployed to staging |
| 09: confidence heatmap and uncertainty, outline correction, millimetre scale marker | Heatmap and correction COMPLETED; marker accuracy waits on real marker photos |
| 10: logs and metrics, load tests, privacy controls, model registry and drift | Built and tested locally; hosted runs wait on a staging deployment |

Per-specification status is in [`specs/MASTER_TRACKER.md`](specs/MASTER_TRACKER.md).

| Measure | Result | Evidence |
|---|---|---|
| FUSeg2021 held-out test, 191 images | Pooled Dice **0.922**, macro Dice **0.841** | [Segmentation report](reports/experiments/spec_02_03_report.md) |
| LowerLimb V3 external check, no tuning | Pooled Dice **0.256** | [Phase 06 report](reports/final/phase_06_validation_report.md) |
| CPU speed | About 5.8 s per image on 2 cores; 97% is segmentation | [Benchmark](reports/final/p06_benchmark.json) |

### Known gaps

- External generalisation is not established. On LowerLimb V3, pooled Dice is 0.26, against 0.92 in-domain. Testing
  showed the different annotation protocol explains part of the drop, not all of it
  ([P09-S04 report](reports/experiments/p09_s04_report.md)).
- Real longitudinal patient series are not available. Trends were exercised with constructed examination sequences only.
- Millimetre values need a scale. Without a printed marker in the photo or a supplied `pixels_per_mm`, only pixel
  values are reported, and the marker's accuracy on real photos is not yet measured.
- No hosted deployment of the full system. The Docker Space needs Hugging Face PRO, and staging needs always-on hosting.
- DFUC2020, DFUC2021 and DFUC2022 are **blocked** pending the official license application.

## Quick start

```bash
python -m pip install -r requirements.txt
```

```bash
python -m pytest -q
```

The tests need no checkpoint or dataset images; a few skip when the FUSeg2021 images are absent.

### Web app in demonstration mode

Needs Node.js. No API, model or sign-in.

```bash
npm --prefix web ci
```

```bash
npm --prefix web run dev:mock
```

Open <http://localhost:3000>. Every page shows constructed data with a banner saying so.

### Full system locally

Place the checkpoint at `models/checkpoints/spec-02-03/resnet34_unet_512_best.pth` (SHA-256 in the
[release guide](docs/release/RELEASE.md)), and have Redis running on port 6379. Then start each of these in its own
terminal:

```bash
node web/e2e/oidc.mjs
```

```bash
DFU_AUTH_ISSUER=http://localhost:8085 DFU_AUTH_AUDIENCE=dfu-api DFU_AUTH_JWKS_URL=http://localhost:8085/jwks DFU_REDIS_URL=redis://127.0.0.1:6379 python -m uvicorn src.api.app:app --port 8000
```

```bash
DFU_REDIS_URL=redis://127.0.0.1:6379 python -m arq src.worker.settings.WorkerSettings
```

```bash
npm --prefix web run dev
```

The first is a local test identity provider, so sign-in needs no account. For the web app, copy `web/.env.example`
to `web/.env.local` and set `AUTH_OIDC_ISSUER=http://localhost:8085` and `AUTH_OIDC_AUDIENCE=dfu-api`. Open
<http://localhost:3000>, sign in, create a case and upload a photo.

### Single service with the original dashboard

```bash
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/dashboard>. The API schema is at `/docs`. To confirm the running system works:

```bash
python scripts/deployment/smoke_test.py
```

### Docker / Hugging Face Spaces

```bash
docker build -f docker/production/Dockerfile -t dfu-woundmonitor .
```

```bash
docker run --rm -p 7860:7860 -v "$PWD/models:/home/user/app/models" dfu-woundmonitor
```

The checkpoint is fetched at container start from a Hugging Face model repo (`DFU_CHECKPOINT_REPO`) and is used only
if its SHA-256 matches the pinned value. Publishing steps: [docs/deployment/HUGGINGFACE.md](docs/deployment/HUGGINGFACE.md).

## How it works

```text
browser (Next.js) → FastAPI /api/v2 → Redis queue → worker: quality gate → segmentation → measurement → stored record
        │                                                        │
        └─ sign-in through OpenID Connect                        └─ rejected: stored with reason codes; the model never runs
```

| Part | Technology |
|---|---|
| Model | ImageNet-pretrained ResNet34 U-Net at 512 px with flip TTA, trained with PyTorch; ONNX Runtime for serving |
| Service | FastAPI, with typed errors and separate health checks for service and model |
| Jobs | Redis with arq workers, so uploads return at once and the model runs in the background |
| Storage | PostgreSQL or SQLite through SQLAlchemy and Alembic, plus a content-addressed blob store |
| Sign-in | OpenID Connect; each user sees only their own cases |
| Web app | Next.js, React and Tailwind CSS, with a typed client generated from the API schema |
| Packaging | Docker image, Hugging Face Space bundle, GitHub Actions CI |

## Repository structure

```text
src/        Application code: data, segmentation, preprocessing, quality, inference,
            measurement, longitudinal, storage, api, worker, dashboard
web/        Next.js web app
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
