# P07-S03 — Object Storage and Pre-Signed Uploads

**Status:** `IN_PROGRESS`. Code complete and verified against a local S3 server (moto). The MinIO CI job has not run yet because nothing has been pushed, and bucket CORS from a real browser waits for P08-S02.

## 1. Objective

Move images and artifacts to S3-compatible storage, so that any instance can read them and uploads bypass the API.

## 2. Scope

- `BlobStore` interface with local and S3 backends
- Pre-signed upload and download URLs
- Upload validation before analysis
- Migration of existing blobs

## 3. Non-Goals

- Automatic deletion, which belongs to P10-S03
- CDN tuning
- Client-side image editing

## 4. Requirements

- `REQ-P07-S03-001`: Storage SHALL sit behind one `BlobStore` interface with local-disk and S3 backends that pass the same tests.
- `REQ-P07-S03-002`: Blobs SHALL stay content-addressed by SHA-256, and a read SHALL verify the hash.
- `REQ-P07-S03-003`: `POST /api/v2/uploads` SHALL return a pre-signed PUT URL that expires within 15 minutes and is limited to 25 MB.
- `REQ-P07-S03-004`: Before analysis, the server SHALL verify the stored object's size, hash and decodable format. The client's declared type SHALL NOT be trusted.
- `REQ-P07-S03-005`: The bucket SHALL be private. Reads SHALL use short-lived URLs issued after an access check.

## 5. Assumptions

- Cloudflare R2 is the default because it charges no egress fee; any S3-compatible store works.
- Tests use a local S3 emulator (MinIO in CI).

## 6. Dependencies

- `P07-S02`

## 7. Inputs

- Existing blobs under `DFU_DATA_DIR/blobs`
- `DFU_S3_ENDPOINT`, `DFU_S3_BUCKET` and credentials from the environment

## 8. Outputs

- S3 backend
- `/api/v2/uploads` routes
- `scripts/deployment/migrate_blobs.py`

## 9. Data / Interface Contract

`POST /api/v2/uploads` takes `{filename, size_bytes, sha256}` and returns `{upload_id, url, expires_at}`. The client PUTs the file. `POST /api/v2/uploads/{id}/verify` checks the stored object and moves it to `VERIFIED` or `REJECTED`. `POST /api/v2/analyses` then takes `upload_id`. It runs synchronously until P07-S05 puts it on the queue. `GET /api/v2/analyses/{id}/artifacts/{kind}` returns a short-lived URL. `/health/ready` gains a required `storage` field.

## 10. Invariants

- Credentials never reach the browser.
- An unverified upload never reaches the model.
- The local backend keeps working for development.

## 11. Technical Design

`BlobStore` exposes `put`, `get`, `exists`, `delete` and `presign`. Object keys derive from the hash, so identical uploads share one object. A row in a new `uploads` table tracks the state: `PENDING`, `VERIFIED` or `REJECTED`. Uploads wait under `uploads/{upload_id}`, outside the content-addressed space, so an unverified file can never be mistaken for a stored one, and `get` refuses any key without a hash. The object is promoted to its content-addressed key only after verification. The S3 upload URL signs `Content-Length`, so the 25 MB limit is enforced by the store. The local backend serves the same contract through HMAC-signed URLs on `/api/v2/blobs/{key}`, keyed by `DFU_BLOB_URL_SECRET`.

## 12. Implementation Tasks

1. Extract the interface from the current store.
2. Add the S3 backend and a MinIO CI service.
3. Add upload routes and verification.
4. Migrate existing blobs and verify every hash.

## 13. Failure Modes / Edge Cases

| Case | Required behaviour |
|---|---|
| Upload never completes | The row expires and the object is removed |
| File larger than declared | `INVALID_INPUT` 413 and the object is deleted |
| Storage unavailable | `INFRASTRUCTURE_FAILURE` 503 |
| Hash mismatch on read | `INFRASTRUCTURE_FAILURE`, logged as corruption |

## 14. Tests

- Shared backend contract tests
- Expiry and size limits
- Disguised and corrupted files

## 15. Acceptance Criteria

- The same contract tests pass on both backends.
- The full analysis flow works with the API holding no image on local disk.

## 16. Evidence

- CI run with MinIO
- Migration report with hash verification

## 17. Reproducibility

```bash
python -m pytest tests/storage -q
python scripts/deployment/migrate_blobs.py --verify
```

## 18. Risks / Limitations

- CORS settings on the bucket are easy to get wrong and must be tested from a browser.
- Pre-signed URLs grant access until they expire, so their lifetime stays short.

## 19. Traceability

| Requirement | Implementation | Test | Evidence | Status |
|---|---|---|---|---|
| `REQ-P07-S03-001` | `src/storage/blobs.py` | `tests/storage/test_blob_contract.py` | Contract tests pass on local disk and moto. MinIO in CI awaits a push | IN_PROGRESS |
| `REQ-P07-S03-002` | `src/storage/blobs.py` | `test_corrupt_blob_detected` | Test run | COMPLETED |
| `REQ-P07-S03-003` | `src/api/uploads.py` | `test_upload_url_limits` | Test run | COMPLETED |
| `REQ-P07-S03-004` | `src/api/uploads.py` | `test_rejects_disguised_file` | Test run | COMPLETED |
| `REQ-P07-S03-005` | `src/storage/blobs.py` | `test_no_public_access` | Test run on moto. A hosted bucket has not been created or reviewed | IN_PROGRESS |
