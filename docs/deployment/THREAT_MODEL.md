# Threat Model

This covers the signed-in service (`/api/v2`, workers, storage and queue) as it stands after P10-S03. It meets
REQ-P10-S03-005: every risk has a decision, either **addressed** with the control and its test, or **accepted** with
the reason.

The service is a research demonstrator. It says it is not for real patient data, and it claims no HIPAA, GDPR or
medical-device compliance. The legal text of the consent notice is the owner's decision before any wide launch.

## System and trust boundaries

```
browser ──HTTPS──► API (FastAPI) ──► database (SQLite or PostgreSQL)
   │                  │    └──────► queue (Redis) ──► worker ──► model
   └──signed PUT/GET──┴──────────► object store (local disk or S3-compatible)
identity provider ──JWKS──► API
```

| Boundary | What crosses it | Trust |
|---|---|---|
| Browser to API | Bearer token, JSON, file metadata | Untrusted |
| Browser to object store | Image bytes, through a signed URL | Untrusted |
| API to identity provider | Public keys only | Trusted for signatures |
| API and worker to database, store and queue | Rows, objects, job IDs | Trusted, private network |

## Upload

| # | Threat | Decision | Control | Evidence |
|---|---|---|---|---|
| U1 | A file that is not an image, or a crafted one, reaches the model | Addressed | Size, SHA-256 and format are checked at verify; only JPEG, PNG and the configured formats decode | `tests/api/test_uploads.py` |
| U2 | Decompression bomb | Addressed | The decoder's pixel limit (50 million by default) rejects it before any work | `tests/integration/test_p03_s01_inference.py` |
| U3 | EXIF GPS, device serials, comments or PNG text leak where the image is | Addressed | `src/preprocessing/sanitise.py` strips metadata at verify; only the clean copy is stored, and its hash is the key | `tests/security/test_p10_s03_metadata.py` |
| U4 | Sanitising changes pixels, so results shift | Addressed | JPEG scan data is kept byte for byte; every output is decoded and compared, with a lossless PNG fallback | same file |
| U5 | Upload flooding fills storage | Addressed | Per-user and per-address rate limits; unverified uploads expire in 15 minutes; retention removes the rest | `tests/security/test_p10_s03_access.py` |
| U6 | A signed upload URL is reused or shared | Accepted | It lasts 10 minutes, covers one key and one size, and verify checks the declared hash. A leaked URL lets someone replace one pending image of that size and hash, which is impossible without the bytes | `tests/api/test_uploads.py` |
| U7 | Someone uploads real patient photos despite the notice | Accepted | Consent text, the notice on every page, and 24-hour retention reduce the harm; the service cannot detect it | Privacy page |

## Storage

| # | Threat | Decision | Control | Evidence |
|---|---|---|---|---|
| S1 | Images kept longer than needed | Addressed | `DFU_RETENTION_HOURS` (default 24) deletes images, results and uploads in cases nobody chose to keep; objects go before rows, so a failed run is retried | `tests/security/test_p10_s03_retention.py` |
| S2 | Retention deletes a case the user wanted for tracking | Addressed | Keeping is an explicit choice per case (`PUT /cases/{id}/keep`), shown in the web app | same file |
| S3 | Deletion fails and objects outlive the limit | Addressed | Rows stay when any object delete fails; the sweep reruns, and the worker logs how many images are overdue | same file |
| S4 | One user reads another's rows or objects | Addressed | Every query is owner-scoped; another user's ID answers 404; artifact links are signed for 5 minutes | `tests/api/test_auth.py` |
| S5 | Account deletion leaves objects behind | Addressed | Delete removes rows and every object not shared with another row | `tests/api/test_auth.py` |
| S6 | Bucket credentials leak | Accepted | They come from the platform's secret store, never the repository; scoping the key to one bucket is the operator's job | Deployment guide |
| S7 | Object store or database is read at rest | Accepted | Encryption at rest is the provider's setting; the service stores no names and no metadata | — |

## Authentication and access

| # | Threat | Decision | Control | Evidence |
|---|---|---|---|---|
| A1 | Forged, expired or foreign tokens | Addressed | RS256 or ES256 only, checked against the provider's JWKS for issuer, audience and expiry; `alg: none` and HS tokens are refused | `tests/api/test_auth.py` |
| A2 | Password theft | Addressed | The service stores no passwords; sign-in is the identity provider's | — |
| A3 | Credential stuffing or brute force against the API | Addressed in part | Per-address limit runs before the token check; the provider owns sign-in limits | `tests/security/test_p10_s03_access.py` |
| A4 | One user exhausts the service | Addressed | Per-user limit after sign-in, 429 with `Retry-After` | same file |
| A5 | Users behind one proxy share an address and block each other | Accepted | The address limit is set five times looser than the user limit, and the user limit does the real work | same file |
| A6 | Rate limits are counted per replica | Accepted | N replicas allow N times the limit. A shared Redis counter is the fix if abuse shows up in the metrics | `src/api/limits.py` |
| A7 | Cross-site requests from another origin | Addressed | No cookies are used, so CSRF does not apply; CORS allows only `DFU_CORS_ORIGINS`, never `*`, and no credentials | same file |
| A8 | The API's JSON is framed or sniffed as HTML | Addressed | `/api`, `/health` and `/metrics` send `default-src 'none'`, `frame-ancestors 'none'`, `X-Frame-Options: DENY` and `nosniff`; HSTS everywhere | same file |
| A9 | The v1 demo has no accounts | Accepted | It is removed whenever `DFU_AUTH_ISSUER` is set, and the dashboard says it is a demonstrator | `docs/api/API.md` |
| A10 | Consent was never given | Addressed | Upload refuses without consent for the current text version; changing the text means everyone accepts again | `tests/security/test_p10_s03_access.py` |

## Queue and workers

| # | Threat | Decision | Control | Evidence |
|---|---|---|---|---|
| Q1 | Queue flooding | Addressed | Submit answers 429 past `DFU_MAX_QUEUE`; rate limits come first | `tests/worker/test_jobs.py` |
| Q2 | A job payload carries data an attacker controls | Addressed | The queue holds only an analysis ID; the worker reads the request from the owner's row | same file |
| Q3 | Redis is reachable from outside | Accepted | It must sit on the private network with a password in `DFU_REDIS_URL`; the service does not open it | Deployment guide |
| Q4 | A poisoned job crashes workers in a loop | Addressed | Model errors do not retry; a lost job is retried once, then fails with `WORKER_LOST` | `tests/worker/test_jobs.py` |
| Q5 | Logs leak images, filenames or tokens | Addressed | The scrubber removes secrets; logs carry IDs, never content | `tests/worker/test_p10_s01_observability.py` |

## Supply chain

| # | Threat | Decision | Control | Evidence |
|---|---|---|---|---|
| D1 | A vulnerable Python or npm dependency | Addressed when CI runs | The `security` CI job runs `pip-audit` and `npm audit --audit-level=critical`, and fails on critical findings | `.github/workflows/ci.yml` |
| D2 | A vulnerable OS package in the image | Addressed when CI runs | Trivy scans the built image and fails on critical findings | same file |
| D3 | A swapped model checkpoint | Addressed | The inference config pins the checkpoint's SHA-256, and the service refuses to serve a mismatch | `scripts/deployment/check_refuses_bad_model.py` |

## Not covered

- A third-party penetration test.
- Abuse detection beyond rate limits.
- Legal review of the consent and privacy text.

Review this document whenever a new route, storage location or external service is added.
