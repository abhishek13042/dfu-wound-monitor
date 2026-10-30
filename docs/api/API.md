# API reference

Two versions run side by side:

- `/api/v2` needs sign-in, keeps each user's data separate, takes uploads through signed URLs and runs analyses as
  background jobs. It answers 503 until `DFU_AUTH_ISSUER` is configured.
- `/api/v1` has no sign-in and runs analyses inside the request. It is for local use and the Hugging Face demo, and
  it is removed, with the dashboard, whenever `DFU_AUTH_ISSUER` is set.

Service version `p05-1.0`. The running service also publishes an interactive schema at `/docs`. The implementation
is `src/api/`, with response models in `src/api/schemas.py`.

Results are image-derived technical measurements. They are not diagnoses and must not guide care.

## Health

| Method | Path | Response |
|---|---|---|
| GET | `/health/live` | 200 while the process is serving |
| GET | `/health/ready` | 200 only when `model`, `database`, `storage` and `queue` are all READY; otherwise 503, with each reported separately |

With a queue configured, `model` is READY when a worker has reported in with the expected model, because the API
process does not load one.

## API v1

### Model

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/model` | Model description, quality and measurement config references, limitations |

### Cases and examinations

| Method | Path | Purpose | Success |
|---|---|---|---|
| POST | `/api/v1/cases` | Create a case | 201 |
| GET | `/api/v1/cases` | List cases | 200 |
| GET | `/api/v1/cases/{case_id}` | Read a case and its examinations | 200 |
| DELETE | `/api/v1/cases/{case_id}` | Delete a case with its examinations, analyses and blobs | 200 |
| POST | `/api/v1/cases/{case_id}/examinations` | Add a dated examination | 201 |
| GET | `/api/v1/examinations/{examination_id}` | Read an examination and its analyses | 200 |

### Analyses

`POST /api/v1/analyses` takes `multipart/form-data`:

| Field | Required | Meaning |
|---|---|---|
| `file` | Yes | PNG, JPEG, BMP, TIFF or WebP image, 25 MB at most |
| `examination_id` | No | Links the analysis to an examination, which must exist |
| `pixels_per_mm` | No | Scale. Measurements are `PHYSICALLY_CALIBRATED` when given and `PIXEL_BASED` otherwise |
| `calibration_method` | No | Defaults to `USER_ENTERED`; needs `pixels_per_mm` |
| `calibration_source` | No | Free-text source of the scale; needs `pixels_per_mm` |
| `threshold` | No | Overrides the model threshold of 0.40 for this request |

A success returns 201 with the measurement, quality result, provenance, warnings, limitation and artifact links.

| Method | Path | Returns |
|---|---|---|
| GET | `/api/v1/analyses/{analysis_id}` | The stored record |
| GET | `/api/v1/analyses/{analysis_id}/image` | The original upload |
| GET | `/api/v1/analyses/{analysis_id}/mask.png` | Binary mask |
| GET | `/api/v1/analyses/{analysis_id}/probability.png` | Probability map |
| GET | `/api/v1/analyses/{analysis_id}/overlay.png?max_side=1024` | Overlay; `max_side` is 64–8192 |

Mask, probability and overlay exist only for completed analyses.

### Longitudinal

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/cases/{case_id}/trend` | Technical trend across examinations. Excluded examinations are listed with reason codes |
| GET | `/api/v1/compare?analysis_a=&analysis_b=` | Pairwise technical comparison under the explicit compatibility policy |

## API v2

Every route except `GET /api/v2/model` needs `Authorization: Bearer <token>`. The service checks the signature,
issuer, audience and expiry against the provider's public keys, and it stores no passwords. An ID that belongs to
someone else returns 404, exactly as an unknown ID does.

| Method | Path | Purpose | Success |
|---|---|---|---|
| GET | `/api/v2/model` | Model description; public | 200 |
| POST, GET | `/api/v2/cases` | Create a case, or list your cases | 201, 200 |
| GET, DELETE | `/api/v2/cases/{case_id}` | Read or delete a case | 200 |
| POST | `/api/v2/cases/{case_id}/examinations` | Add a dated examination | 201 |
| GET | `/api/v2/examinations/{examination_id}` | Read an examination | 200 |
| GET | `/api/v2/cases/{case_id}/trend` | Technical trend | 200 |
| GET | `/api/v2/compare?analysis_a=&analysis_b=` | Pairwise technical comparison | 200 |
| POST | `/api/v2/uploads` | Get a signed upload URL | 201 |
| POST | `/api/v2/uploads/{upload_id}/verify` | Check the stored file's size, hash and format | 200 |
| POST | `/api/v2/analyses` | Queue an analysis | 202 |
| GET | `/api/v2/analyses/{analysis_id}` | Job status, or the result once finished | 200 |
| GET | `/api/v2/analyses/{analysis_id}/artifacts/{kind}` | Signed link to `image`, `mask` or `probability` | 200 |
| GET | `/api/v2/account/export` | Everything stored for you | 200 |
| DELETE | `/api/v2/account` | Delete your account, rows and blobs | 200 |

### Running an analysis

1. `POST /api/v2/uploads` with `filename`, `size_bytes` and `sha256`. Send the file to the returned URL.
2. `POST /api/v2/uploads/{upload_id}/verify`.
3. `POST /api/v2/analyses` with `upload_id`, and optionally `examination_id`, `pixels_per_mm`, `calibration_method`,
   `calibration_source` and `threshold`. The response is 202 with `analysis_id` and `status: QUEUED`.
   Submitting the same upload twice returns the same job.
4. Poll `GET /api/v2/analyses/{analysis_id}`.

| Status | Meaning | Body |
|---|---|---|
| `QUEUED` | Waiting for a worker | `analysis_id`, `status` |
| `RUNNING` | A worker holds the job | `analysis_id`, `status` |
| `COMPLETED` | Finished | The full analysis, as in v1 |
| `QUALITY_REJECTED` | The image failed the quality gate; segmentation did not run | The stored analysis |
| `FAILED` | The job stopped | `analysis_id`, `status`, and `error` with the standard fields |

Infrastructure failures retry after 5, 20 and 60 seconds. Bad inputs and model errors do not retry. A job left in
`RUNNING` for 10 minutes goes back on the queue once, and a second loss fails it with code `WORKER_LOST`. A `FAILED`
row with its `error` is the dead-letter record.

## Errors

Every error uses one body:

```json
{
  "error": {
    "category": "QUALITY_REJECTED",
    "failure_class": "QUALITY",
    "code": "QUALITY_REJECTED",
    "message": "Image rejected by the quality gate: ...",
    "details": {}
  },
  "request_id": null,
  "analysis": null
}
```

| Category | HTTP | Failure class | Meaning |
|---|---|---|---|
| `INVALID_INPUT` | 400 | INPUT | Bad request, or an undecodable or disallowed image |
| `INVALID_INPUT` | 413 | INPUT | Upload is too large |
| `UNAUTHENTICATED` | 401 | INPUT | The token is missing, forged, expired, or for another issuer or audience |
| `NOT_FOUND` | 404 | INPUT | Unknown case, examination or analysis, or one owned by someone else |
| `CONFLICT` | 409 | PERSISTENCE | A write violates an integrity constraint |
| `QUALITY_REJECTED` | 422 | QUALITY | The image failed the quality gate; segmentation did not run |
| `BUSY` | 429 | SERVICE | The queue is full (`QUEUE_FULL`). `Retry-After` says when to try again |
| `MODEL_FAILURE` | 500 | MODEL | The model failed on an accepted image |
| `MODEL_NOT_READY` | 503 | MODEL | The model artifact is not loaded, or no worker is running |
| `INFRASTRUCTURE_FAILURE` | 503 | PERSISTENCE, or SERVICE for an unexpected error | Database, storage or queue failed. A job that could not be queued leaves no row behind |

Quality-rejected and failed analyses are stored for audit, and the error body includes the stored `analysis`.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DFU_DATA_DIR` | `runtime/` | Location of the default SQLite database and blob store |
| `DFU_DATABASE_URL` | SQLite under `DFU_DATA_DIR` | PostgreSQL URL. Run `scripts/deployment/migrate_db.py` first |
| `DFU_STORAGE_BACKEND` | `local` | `local` or `s3` |
| `DFU_S3_BUCKET`, `DFU_S3_ENDPOINT` | none | Bucket, and endpoint for a non-AWS store such as R2 or MinIO. Credentials come from the standard AWS variables |
| `DFU_BLOB_URL_SECRET` | random per process | Signs URLs for the local backend. Set it when several processes share a data directory |
| `DFU_INFERENCE_CONFIG` | `configs/inference/spec_02_03_inference.json` | Inference config, which pins the checkpoint hash |
| `DFU_AUTH_ISSUER`, `DFU_AUTH_AUDIENCE`, `DFU_AUTH_JWKS_URL` | none | Turn on `/api/v2`. Setting the issuer also removes `/api/v1` and the dashboard |
| `DFU_REDIS_URL` | none | Queue URL. When set, the API loads no model and workers run the analyses |
| `DFU_MAX_QUEUE` | `100` | Waiting jobs before submit answers 429 |
| `DFU_ROLE` | `api` | In the Docker image, `worker` starts a worker |

The Docker image has its own settings; see [Hugging Face deployment](../deployment/HUGGINGFACE.md).

## Current limits

- `/api/v1` has no authentication, so it must not be exposed with real data.
- The signed-in flow has not been run against a real identity provider. The tests use locally generated keys.
- With `DFU_REDIS_URL` set, the API process holds no model, so `POST /api/v1/analyses` answers 503. Use `/api/v2`.
- With the local storage backend, the API and the worker must share a disk.
- Each worker runs one job at a time, and the model's memory limits the workers per machine.

Phases 07–10 address these. See the [production roadmap](../roadmap/PRODUCTION_ROADMAP.md).
