# P10-S03 — Security and Privacy Controls

**Status:** `COMPLETED`. Retention with a per-case keep choice, metadata stripping, recorded consent, per-user and per-address rate limits, strict headers, CORS and the threat model are built, with 26 local tests, and the web app shows the consent step, the keep control and a privacy page. The `security` CI job passes (Actions run 42579066019, 2026-11-09) after the owner approved upgrading Pillow, pytest, setuptools and `next`.

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
- [Actions run 42579066019](https://github.com/abhishek13042/dfu-wound-monitor/actions/runs/42579066019) on [PR #1](https://github.com/abhishek13042/dfu-wound-monitor/pull/1), commit `49ca385`, recorded on 2026-11-09: the `security` job passes.
  - `pip-audit -r requirements.txt`: no known vulnerabilities. Run 42478962863 had found 81 in Pillow 12.0.0,
    pytest 8.3.5 and setuptools 81.0.0; they are now pinned at 13.0.0, 9.0.3 and 84.1.0.
  - `npm audit --audit-level=critical`: passes. `next` is now 15.5.29. 9 advisories below critical remain
    (2 high, 5 moderate, 2 low), in `sharp` and `postcss` nested under `next` and in packages pulled in by
    `shadcn`: `reports/final/p10_s03_npm_audit.json`.
  - Trivy on the API image, critical and fixable only: 0 findings (Debian 13.7 base and Python packages):
    `reports/final/p10_s03_trivy.txt`.
  - Pillow 13 needed one typing change: `load_binary_mask` passes `resize` an explicit `(width, height)`.
- Web: `tsc`, 25 unit tests, the wording check and the 45-test Playwright pages suite (axe at 1280 and 375 px, now with
  `/privacy`) pass. `npx impeccable detect` is clean on `/privacy`, `/analyse`, `/cases/c-0007` and `/account`.

## 17. Reproducibility

```bash
python -m pytest tests/security -q
npm --prefix web audit --audit-level=critical          # passes; 2 high, 5 moderate, 2 low remain
pip-audit -r requirements.txt                          # run in CI; not installed locally
trivy image --severity CRITICAL --ignore-unfixed dfu-api   # run in CI; not installed locally
```

Retention runs in the worker's sweep (`src/worker/tasks.py`, `retain`), so it needs no separate scheduler.

## 18. Risks / Limitations

- The job fails only on critical npm and image findings. Two high-severity npm advisories (in `sharp` and `postcss`
  under `next`) stay open until `next` ships with patched copies; they are build-time image and CSS tooling, not
  request handling.

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
| `REQ-P10-S03-006` | `security` job in `.github/workflows/ci.yml` | CI job | Actions run 42579066019 (commit `49ca385`): `security` job passes. `pip-audit` finds no known vulnerabilities after Pillow 13.0.0, pytest 9.0.3 and setuptools 84.1.0; `npm audit --audit-level=critical` passes after `next` 15.5.29 (2 high, 5 moderate, 2 low remain); Trivy finds no fixable critical finding in the image | COMPLETED |
