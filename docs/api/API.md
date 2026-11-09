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

A completed analysis carries `inference.uncertainty` (P09-S02): how much the four flip views disagree, inside the outline and an 8-pixel band. It is `null` when TTA is off. Show the value only when its `summary_shown` is true; it is model uncertainty, not a chance that the result is correct.

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
| GET, POST | `/api/v2/consent` | Read the consent text version, or accept it | 200 |
| GET, PUT | `/api/v2/cases/{case_id}/keep` | Read or set whether retention leaves this case alone | 200 |
| POST | `/api/v2/uploads` | Get a signed upload URL. Needs consent first | 201 |
| POST | `/api/v2/uploads/{upload_id}/verify` | Check the stored file's size, hash and format | 200 |
| POST | `/api/v2/analyses` | Queue an analysis | 202 |
| GET | `/api/v2/analyses/{analysis_id}` | Job status, or the result once finished | 200 |
| GET | `/api/v2/analyses/{analysis_id}/artifacts/{kind}` | Signed link to `image`, `mask` or `probability` | 200 |
| POST, GET | `/api/v2/analyses/{analysis_id}/corrections` | Save a corrected outline as a new version, or list the versions | 201, 200 |
| GET | `/api/v2/corrections/{correction_id}/mask` | Signed link to a corrected mask | 200 |
| PUT | `/api/v2/corrections/{correction_id}/research` | Share a correction for research, or withdraw it: `{"opt_in": bool}` | 200 |
| GET | `/api/v2/account/export` | Everything stored for you | 200 |
| DELETE | `/api/v2/account` | Delete your account, rows and blobs | 200 |

### Running an analysis

0. Once per user, `POST /api/v2/consent` with the `text_version` that `GET /api/v2/consent` reports. Without it,
   step 1 answers 403 `CONSENT_REQUIRED`; an old version answers 409 `CONSENT_VERSION_CHANGED`.
1. `POST /api/v2/uploads` with `filename`, `size_bytes` and `sha256`. Send the file to the returned URL.
2. `POST /api/v2/uploads/{upload_id}/verify`. EXIF, GPS, comments and PNG text are removed here, and only that copy
   is stored. Pixels do not change; a JPEG with an EXIF rotation is stored as a PNG of the rotated pixels.
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

### Correcting an outline

`POST /api/v2/analyses/{analysis_id}/corrections` takes multipart `file`, a PNG the same size as the image with every
pixel black (0) or white (255) and opaque, and optional `research_opt_in` (default `false`). The service measures it
with the same engine and calibration as the analysis and returns 201 with `correction_id`, `version`, `author`,
`created_at`, `sha256`, `measurement` and `research_opt_in`. The analysis and its mask never change.

Bad masks answer 400 `INVALID_INPUT` with `MASK_NOT_PNG`, `MASK_SIZE_MISMATCH`, `MASK_NOT_GRAYSCALE` or `MASK_VALUES`;
a mask over the upload limit answers 413 `MASK_TOO_LARGE`, and an analysis that is not completed answers 409
`ANALYSIS_NOT_COMPLETED`. Trend rows carry `mask_source` (`MODEL` or `CORRECTED`) and `correction_id`, and use the
latest correction. The account export lists every correction; research use needs the opt-in.

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
| `INVALID_INPUT` | 403 | INPUT | Consent has not been accepted (`CONSENT_REQUIRED`) |
| `BUSY` | 429 | SERVICE | The queue is full (`QUEUE_FULL`), or a rate limit was hit (`RATE_LIMITED`). `Retry-After` says when to try again |
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
| `DFU_S3_BUCKET`, `DFU_S3_ENDPOINT` | none | Bucket, and endpoint for a non-AWS store such as R2 or SeaweedFS. Credentials come from the standard AWS variables |
| `DFU_BLOB_URL_SECRET` | random per process | Signs URLs for the local backend. Set it when several processes share a data directory |
| `DFU_INFERENCE_CONFIG` | `configs/inference/spec_02_03_inference.json` | Inference config, which pins the checkpoint hash |
| `DFU_AUTH_ISSUER`, `DFU_AUTH_AUDIENCE`, `DFU_AUTH_JWKS_URL` | none | Turn on `/api/v2`. Setting the issuer also removes `/api/v1` and the dashboard |
| `DFU_REDIS_URL` | none | Queue URL. When set, the API loads no model and workers run the analyses |
| `DFU_MAX_QUEUE` | `100` | Waiting jobs before submit answers 429 |
| `DFU_ROLE` | `api` | In the Docker image, `worker` starts a worker |
| `DFU_RETENTION_HOURS` | `24` | Images, results and uploads older than this are deleted, except in kept cases. `0` keeps everything |
| `DFU_RATE_LIMIT_USER` | `120` | Requests per minute per signed-in user. `0` turns it off |
| `DFU_RATE_LIMIT_IP` | `600` | Requests per minute per client address on `/api/`, before sign-in. `0` turns it off |
| `DFU_CORS_ORIGINS` | none | Comma-separated origins allowed to call the API from a browser. Without it, no CORS headers are sent |

The Docker image has its own settings; see [Hugging Face deployment](../deployment/HUGGINGFACE.md).

## Current limits

- `/api/v1` has no authentication, so it must not be exposed with real data.
- The signed-in flow has not been run against a real identity provider. The tests use locally generated keys.
- With `DFU_REDIS_URL` set, the API process holds no model, so `POST /api/v1/analyses` answers 503. Use `/api/v2`.
- With the local storage backend, the API and the worker must share a disk.
- Each worker runs one job at a time, and the model's memory limits the workers per machine.
- Rate limits are counted in each API process, so N replicas allow up to N times the limit.
- The client address is the one the server sees. Behind a proxy, run uvicorn with `--proxy-headers` and a trusted
  `--forwarded-allow-ips`, or every user shares the proxy's address.

Phases 07–10 address these. See the [production roadmap](../roadmap/PRODUCTION_ROADMAP.md).
