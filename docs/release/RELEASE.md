# DFU-WoundMonitor: release guide (research prototype)

> This is a research prototype. It is not a medical device and has not been clinically validated.
> Its outputs are image-derived technical measurements of a segmented region. They must not be used
> for diagnosis or treatment decisions.

## What ships

| Component | Version / identifier |
|---|---|
| Segmentation model | `spec-02-03-resnet34-unet-512-v1` (ResNet34 U-Net, 512 px, threshold 0.40, min area 128, flip TTA) |
| Inference config | `configs/inference/spec_02_03_inference.json` |
| Quality gate | `configs/quality/` (calibrated in `reports/quality/quality_gate_calibration.json`) |
| Measurement | `configs/measurement/measurement_v1.json` |
| Service / API | service `p05-1.0`, API `/api/v1` (FastAPI, SQLite + content-addressed blob store) |
| Dashboard | `/dashboard` (static page that only uses the public API) |

`reports/final/release_manifest.json` lists every version string, the SHA-256 of each config, the git
commit and the evidence files. Rebuild it with
`python scripts/deployment/build_release_manifest.py` (add `--output PATH` to write elsewhere; the tests do this).
`git.dirty` ignores the manifest file itself, so rebuild after committing everything else and it records `false`.

## 1. Install

Requires Python 3.11+ (verified with 3.14 on Windows 11, CPU only).

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/macOS: source .venv/bin/activate)
python -m pip install -r requirements.txt
```

## 2. Place and verify the checkpoint

The 293 MB checkpoint is not in git. Copy it to
`models/checkpoints/spec-02-03/resnet34_unet_512_best.pth`. The expected SHA-256 is:

```
26aca52e401f23b5781d2596d74c1fd7fa86a6af0ab9fb3db9fa17dcffb5cf04
```

The service hashes the file at startup and will not load a file with a different hash. In that
case `/health/ready` reports the model as `NOT_READY` and gives the reason.

## 3. Start

```bash
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

- `DFU_DATA_DIR` sets where the SQLite database and blobs are stored (default `runtime/`, which is gitignored).
  On first start the schema migrations run.
- Startup takes about 1–2 minutes on CPU, because the checkpoint is hashed and then loaded.

## 4. Health

| Endpoint | Meaning |
|---|---|
| `GET /health/live` | The process is up (always 200 while serving). |
| `GET /health/ready` | 200 only when **both** the model and the database are READY. Otherwise 503, with `model` and `database` reported separately. |

## 5. Smoke test

```bash
python scripts/deployment/smoke_test.py                          # in-process, fresh empty data dir
python scripts/deployment/smoke_test.py --url http://127.0.0.1:8000   # against a running server
```

It checks liveness, readiness, model version, checkpoint checksum, one end-to-end analysis, that
the mask artifact is served, that the record persists, and that a blank image is rejected as a
quality failure rather than a model failure.

## 6. API summary

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/model` | Model, config and checksum provenance plus limitations |
| POST/GET | `/api/v1/cases` | Create / list cases |
| GET/DELETE | `/api/v1/cases/{id}` | Read / delete a case (also deletes its examinations, analyses and blobs) |
| POST | `/api/v1/cases/{id}/examinations` | Add a dated examination |
| POST | `/api/v1/analyses` | Upload an image (multipart `file`; optional `examination_id`, `pixels_per_mm`, calibration fields) |
| GET | `/api/v1/analyses/{id}` (+ `/image`, `/mask.png`, `/probability.png`, `/overlay.png`) | Stored record and artifacts |
| GET | `/api/v1/cases/{id}/trend` | Technical trend across examinations |
| GET | `/api/v1/compare?analysis_a=&analysis_b=` | Pairwise technical comparison |

Every error has the same body: `category`, `code`, `message` and `failure_class`. The failure class is one of
`INPUT` (400/404/413), `QUALITY` (422), `MODEL` (500/503), `PERSISTENCE` (409/503) or `SERVICE` (503).
Quality-rejected and failed analyses are still stored, so they can be audited. The interactive schema is at `/docs`.

## 7. Evidence

| Evidence | File |
|---|---|
| Held-out segmentation (Phase 02) | `reports/experiments/spec_02_03_report.md` |
| End-to-end validation (P06-S01) | `reports/final/phase_06_validation_report.md`, `reports/final/p06_validation_*.json` |
| Reliability and performance (P06-S02) | `reports/final/p06_benchmark.json` |

## 8. Limitations

- Trained and evaluated only on FUSeg2021 images. Performance on other cameras, skin tones, wound types and
  acquisition protocols has not been established. On the external LowerLimb V3 check, Dice drops from 0.92 to 0.26. Much of this drop appears to come
  from a different annotation protocol, but that is a hypothesis (see `reports/final/phase_06_validation_report.md`).
- Physical units (mm, mm²) are only as good as the `pixels_per_mm` calibration supplied. Without it,
  only pixel values are reported.
- Trends and comparisons describe the segmented region in the images. They are not assessments of
  wound progression and must not be used to guide care.
- CPU inference takes several seconds per image. No latency requirement has been set, and no optimisation has been applied.

## 9. Release checklist

- [ ] `python -m pytest -q` passes
- [ ] Checkpoint SHA-256 matches the value above
- [ ] `python scripts/deployment/build_release_manifest.py` exits 0 (model verified, evidence present)
- [ ] `python scripts/deployment/smoke_test.py` reports all checks passed
- [ ] Limitations are shown in `/api/v1/model` and on the dashboard
- [ ] All other changes are committed, then the manifest is rebuilt (`git.dirty: false`), committed and the release tagged
