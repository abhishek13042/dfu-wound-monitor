# P10-S03 — Security and Privacy Controls

**Status:** `IN_PROGRESS`. Retention with a per-case keep choice, metadata stripping, recorded consent, per-user and per-address rate limits, strict headers, CORS and the threat model are built, with 26 local tests, and the web app shows the consent step, the keep control and a privacy page. REQ-P10-S03-006 is `BLOCKED`: the `security` CI job exists but has not run, `pip-audit` and Trivy are not installed here, and `npm audit` already reports one critical advisory in `next@15.5.9` that would fail the job until `next` is upgraded.

## 1. Objective

Apply the privacy and abuse controls that a public image service needs.

## 2. Scope

- Automatic deletion of uploads
- EXIF and metadata removal
- Consent record
- Per-user and per-IP rate limits
- Security headers and CORS
- Threat model and dependency scanning

## 3. Non-Goals

- HIPAA, GDPR or medical device certification claims
- Accepting real patient data
- Penetration testing by a third party

## 4. Requirements

- `REQ-P10-S03-001`: Uploads and artifacts SHALL be deleted automatically after a configured period (default 24 hours), unless the user chose to keep them.
- `REQ-P10-S03-002`: EXIF and other metadata SHALL be removed before storage, and the original bytes SHALL NOT be kept.
- `REQ-P10-S03-003`: Consent SHALL be recorded with text version and time before the first upload.
- `REQ-P10-S03-004`: Rate limits SHALL apply per user and per IP, returning 429 with `Retry-After`.
- `REQ-P10-S03-005`: A threat model SHALL cover upload, storage, auth and queue, with each risk addressed or accepted.
- `REQ-P10-S03-006`: CI SHALL scan dependencies and images, and SHALL fail on critical findings.

## 5. Assumptions

- The service states that it is not for real patient data.
- Legal review of consent text is the owner's decision before any wide launch.

## 6. Dependencies

- `P07-S03`
- `P07-S04`
- `P08-S02`

## 7. Inputs

- Upload pipeline
- Retention settings

## 8. Outputs

- Retention job
- Sanitiser
- Consent table
- Threat model
- Privacy page

## 9. Data / Interface Contract

`DFU_RETENTION_HOURS` sets retention. Sanitising changes file bytes, so the stored hash is taken after sanitising, and pixel values stay unchanged.

## 10. Invariants

- The sanitised file is the only stored copy.
- Deleted data leaves no blob.
- Rate-limit data holds no image content.

## 11. Technical Design

Sanitising re-encodes without metadata; PNG and other lossless formats keep their pixels, while JPEG uses a lossless metadata strip so that results do not shift. Retention runs on a schedule and deletes storage objects before rows, so a failure can be safely re-run.

## 12. Implementation Tasks

1. Add sanitising.
2. Add retention.
3. Add consent.
4. Add rate limits.
5. Write the threat model.
6. Add scanning.

## 13. Failure Modes / Edge Cases

| Case | Required behaviour |
|---|---|
| Deletion fails partway | The job retries, and a report flags objects older than the limit |
| Decompression bomb | Rejected by the existing pixel limit |
| Shared IP | Per-user limits apply after sign-in |

## 14. Tests

- GPS-tagged test image
- Retention including blobs
- Limit bursts
- Security headers

## 15. Acceptance Criteria

- No EXIF survives in storage, and no blob outlives its limit plus one job cycle.
- Each threat has a recorded decision.

## 16. Evidence

Recorded on 2026-11-05.

- `python -m pytest tests/security -q`: 26 passed.
  - `tests/security/test_p10_s03_retention.py`: old rows and objects go, kept cases stay, un-keeping hands a case back
    to retention, a failed object delete keeps the rows for the next pass, and `DFU_RETENTION_HOURS=0` turns it off.
  - `tests/security/test_p10_s03_metadata.py`: GPS EXIF, JPEG comments and PNG `tEXt`, `iTXt` and `eXIf` chunks are
    gone from the stored blob, and the decoded pixels are identical to the upload's.
  - `tests/security/test_p10_s03_access.py`: consent before upload, version changes, per-user records, export,
    429 with `Retry-After`, bounded limiter memory, strict headers, CORS.
- `docs/deployment/THREAT_MODEL.md`: 32 risks across upload, storage, auth, queue and supply chain, each addressed or
  accepted with its evidence.
- `reports/final/p10_s03_npm_audit.json`: 9 advisories (1 critical, 2 high, 4 moderate, 2 low). The critical one is in
  `next@15.5.9` and has a fix in a later 15.x release.
- Web: `tsc`, 25 unit tests, the wording check and the 45-test Playwright pages suite (axe at 1280 and 375 px, now with
  `/privacy`) pass. `npx impeccable detect` is clean on `/privacy`, `/analyse`, `/cases/c-0007` and `/account`.

## 17. Reproducibility

```bash
python -m pytest tests/security -q
npm --prefix web audit --audit-level=critical          # fails today on next@15.5.9
pip-audit -r requirements.txt                          # not installed locally
trivy image --severity CRITICAL --ignore-unfixed dfu-api   # not installed locally
```

Retention runs in the worker's sweep (`src/worker/tasks.py`, `retain`), so it needs no separate scheduler.

## 18. Risks / Limitations

- Automatic deletion conflicts with longitudinal use, so keeping data needs an explicit choice. Compliance is not claimed.
- Rate limits are counted per replica, so N replicas allow N times the limit. A shared Redis counter is the fix if
  abuse shows up.
- The consent text and privacy page are written in the product's plain language and have had no legal review.
- The `security` CI job fails on any `pip-audit` finding, which is stricter than critical-only, because `pip-audit`
  reports no severity.

## 19. Traceability

| Requirement | Implementation | Test | Evidence | Status |
|---|---|---|---|---|
| `REQ-P10-S03-001` | `src/worker/tasks.py` (`retain`), `Repository.apply_retention`, `/cases/{id}/keep`, `web/components/KeepToggle.tsx` | `test_old_records_and_their_objects_are_deleted`, `test_a_kept_case_is_left_alone`, `test_a_failed_object_delete_keeps_the_rows_for_the_next_run` | Test run 2026-11-05 | COMPLETED |
| `REQ-P10-S03-002` | `src/preprocessing/sanitise.py`, verify in `src/api/uploads.py` | `test_gps_jpeg_loses_its_exif_and_keeps_every_pixel`, `test_only_the_clean_copy_is_stored` | Test run 2026-11-05 | COMPLETED |
| `REQ-P10-S03-003` | `src/api/consent.py`, migration `0005_retention_and_consent`, `web/components/UploadForm.tsx` | `test_upload_needs_consent_first`, `test_an_old_consent_version_is_refused` | Test run 2026-11-05 | COMPLETED |
| `REQ-P10-S03-004` | `src/api/limits.py` | `test_address_limit_answers_429_with_retry_after`, `test_user_limit_counts_each_user_apart` | Test run 2026-11-05 | COMPLETED |
| `REQ-P10-S03-005` | `docs/deployment/THREAT_MODEL.md` | Document review | Threat model | COMPLETED |
| `REQ-P10-S03-006` | `security` job in `.github/workflows/ci.yml` | CI job | `reports/final/p10_s03_npm_audit.json` | BLOCKED: job not run; `pip-audit` and Trivy not installed; critical `next` advisory open |
